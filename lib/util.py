import numpy as np
import math
from scipy.sparse import csr_matrix, identity, csgraph, identity
import itertools
import networkx
import time
import matplotlib.pyplot as plt
from operator import itemgetter
import cPickle as pickle


def get_watershed_nr_by_rc(watersheds, landscape, r, c):
    # Simple help method

    mapping = map_nodes_to_watersheds(watersheds, landscape.ny, landscape.nx)
    ix = map_2d_to_1d((r, c), landscape.nx)
    w_nr = mapping[ix]

    return w_nr


def fill_single_cell_depressions(heights, rows, cols):
    """
    Preprocessing to reduce local minima in the terrain.
    :param heights: Heights of the landscape.
    :param rows: Nr of interior nodes in x-dir
    :param cols: Nr of interior nodes in y-dir
    :return heights: Updated heights with single cell depressions removed
    """

    nbr_heights = get_neighbor_heights(heights, rows, cols, d4=False)  # Careful for this d4=False!!!
    delta = np.repeat(heights[1:-1, 1:-1, np.newaxis], 8, axis=2) - nbr_heights[1:-1, 1:-1]
    local_minima = np.where(np.max(delta, axis=2) < 0)  # The single cell depressions to be raised

    # Coords of local minima is for the interior, need to map to exterior
    local_minima = (local_minima[0] + 1, local_minima[1] + 1)

    raised_elevations = np.min(nbr_heights[local_minima], axis=1)  # The elevations they are raised to
    heights[local_minima] = raised_elevations

    return heights


def get_neighbor_heights(heights, rows, cols, d4):
    """
    Returns the heights of the neighbors for all nodes
    :param heights: Heights of the landscape
    :param rows: Number of rows in the 2D-grid
    :param cols: Number of columns in the 2D-grid
    :param d4: Use the D4-method instead of D8
    :return nbr_heights: nx x ny x 8 grid
    """

    if d4:
        nbr_heights = np.empty((rows, cols, 4), dtype=object)

        nbr_heights[1:-1, 1:-1, 0] = heights[1:-1, 2:]      # 1 (2)
        nbr_heights[1:-1, 1:-1, 1] = heights[2:, 1:-1]      # 2 (8)
        nbr_heights[1:-1, 1:-1, 2] = heights[1:-1, 0:-2]    # 3 (32)
        nbr_heights[1:-1, 1:-1, 3] = heights[0:-2, 1:-1]    # 4 (128)
    else:
        nbr_heights = np.empty((rows, cols, 8), dtype=object)

        nbr_heights[1:-1, 1:-1, 0] = heights[0:-2, 2:]    # 1
        nbr_heights[1:-1, 1:-1, 1] = heights[1:-1, 2:]    # 2
        nbr_heights[1:-1, 1:-1, 2] = heights[2:, 2:]      # 4
        nbr_heights[1:-1, 1:-1, 3] = heights[2:, 1:-1]    # 8
        nbr_heights[1:-1, 1:-1, 4] = heights[2:, 0:-2]    # 16
        nbr_heights[1:-1, 1:-1, 5] = heights[1:-1, 0:-2]  # 32
        nbr_heights[1:-1, 1:-1, 6] = heights[0:-2, 0:-2]  # 64
        nbr_heights[1:-1, 1:-1, 7] = heights[0:-2, 1:-1]  # 128

    return nbr_heights


def get_neighbor_indices(indices, cols, d4):
    """
    Given a list of neighbors, returns their neighbor indices
    :param indices: Array of indices
    :param cols: Nr of columns
    :param d4: Use the D4-method instead of D8
    :return nbrs: The neighbors
    """

    if d4:
        nbrs = np.zeros((len(indices), 4), dtype=int)

        nbrs[:, 0] = indices + 1
        nbrs[:, 1] = indices + cols
        nbrs[:, 2] = indices - 1
        nbrs[:, 3] = indices - cols
    else:
        nbrs = np.zeros((len(indices), 8), dtype=int)

        nbrs[:, 0] = indices - cols + 1
        nbrs[:, 1] = indices + 1
        nbrs[:, 2] = indices + cols + 1
        nbrs[:, 3] = indices + cols
        nbrs[:, 4] = indices + cols - 1
        nbrs[:, 5] = indices - 1
        nbrs[:, 6] = indices - cols - 1
        nbrs[:, 7] = indices - cols

    return nbrs


def get_domain_boundary_indices(cols, rows):

    top = np.arange(0, cols, 1, dtype=int)
    bottom = np.arange(cols * rows - cols, cols * rows, 1, dtype=int)
    left = np.arange(cols, cols * rows - cols, cols, dtype=int)
    right = np.arange(2 * cols - 1, cols * rows - 1, cols, dtype=int)

    boundary_indices = np.concatenate((top, bottom, left, right))
    boundary_indices.sort()

    return boundary_indices


def get_domain_boundary_coords(cols, rows):
    """
    Returns the coordinates of the domain boundary as a tuple (rows, cols) consisting of
    numpy arrays.
    :param cols: Nr of grid points in x-dir
    :param rows: Nr of grid points in y-dir
    :return boundary_coordinates: Coordinates of domain boundary
    """

    top = (np.zeros(cols, dtype=int), np.arange(0, cols, 1))
    bottom = (np.ones(cols, dtype=int) * (rows - 1), np.arange(0, cols, 1))
    left = (np.arange(1, rows - 1, 1), np.zeros(rows - 2, dtype=int))
    right = (np.arange(1, rows - 1, 1), np.ones(rows - 2, dtype=int) * (cols - 1))

    boundary_coordinates = (np.concatenate([top[0], bottom[0], left[0], right[0]]),
                            np.concatenate([top[1], bottom[1], left[1], right[1]]))

    return boundary_coordinates


def get_derivatives(heights, nbr_heights, step_size, d4):
    """
    Returns the derivatives as a r x c x 8 grid, where all boundary coordinates
    have None as derivatives. (r x c x 4 if d4 method)
    :param heights:
    :param nbr_heights:
    :param step_size: Step size in the grid
    :param d4: Use the D4-method instead of D8
    :return derivatives: The slope to the neighbors for all nodes, nx x ny x 8 (nx x ny x 4)
    """

    (r, c) = np.shape(heights)

    if d4:
        delta = np.repeat(heights[1:-1, 1:-1, np.newaxis], 4, axis=2) - nbr_heights[1:-1, 1:-1]
        distance = np.ones(4) * step_size
        calc_derivatives = np.divide(delta, distance)
        derivatives = np.empty((r, c, 4), dtype=object)
    else:
        card = step_size
        delta = np.repeat(heights[1:-1, 1:-1, np.newaxis], 8, axis=2) - nbr_heights[1:-1, 1:-1]
        diag = math.sqrt(step_size ** 2 + step_size ** 2)
        distance = np.array([diag, card, diag, card, diag, card, diag, card])
        calc_derivatives = np.divide(delta, distance)
        derivatives = np.empty((r, c, 8), dtype=object)

    derivatives[1:-1, 1:-1] = calc_derivatives

    return derivatives


def get_flow_directions(heights, step_size, rows, cols, d4):
    """
    Returns the steepest directions for all nodes and setting -1 for local minima and flat areas
    :param heights: The heights for all nodes in the 2D-grid
    :param step_size: Step size in the grid
    :param rows: Nr of rows
    :param cols: Nr of columns
    :param d4: Use the D4-method instead of D8
    :return: flow_directions: The neighbor index indicating steepest slope
    """

    if d4:
        nbr_heights = get_neighbor_heights(heights, rows, cols, d4=True)
        derivatives = get_derivatives(heights, nbr_heights, step_size, d4=True)
    else:
        nbr_heights = get_neighbor_heights(heights, rows, cols, d4=False)
        derivatives = get_derivatives(heights, nbr_heights, step_size, d4=False)

    flow_directions = np.empty((rows, cols), dtype=object)
    flow_directions[1:-1, 1:-1] = -1

    pos_derivatives = np.max(derivatives, axis=2) > 0
    flow_directions[pos_derivatives] = np.argmax(derivatives, axis=2)[pos_derivatives]

    if not d4:
        flow_directions[pos_derivatives] = 2 ** flow_directions[pos_derivatives]
    else:
        flow_directions[pos_derivatives] += 1

    return flow_directions


def make_sparse_node_conn_matrix(flow_direction_indices, rows, cols):
    """
    Returns a sparse connectivity matrix for the nodes using information about flow directions
    :param flow_direction_indices: 2D-array of flow directions in the grid
    :param rows: Nr of rows in grid
    :param cols: Nr of cols in grid
    :return node_conn_mat: Sparse node connectivity matrix
    """

    flow_to = np.reshape(flow_direction_indices, rows * cols)

    # Remove -1 and None indices
    indices = np.arange(0, rows * cols, 1)
    keep_indices = flow_to > 0

    # Data for csr-matrix
    flow_from = indices[keep_indices]
    flow_to = flow_to[keep_indices]
    data = np.ones(len(flow_from), dtype=int)

    node_conn_mat = csr_matrix((data, (flow_from, flow_to)), shape=(rows * cols, rows * cols))

    return node_conn_mat


def remove_out_of_boundary_flow(flow_directions, d4):
    """
    Replaces flow out of the boundary by flagging node as minimum/flat area (-1)
    :param flow_directions: The directions of flow for every node
    :param d4: Use the D4-method instead of D8
    :return: Void function that alters flow_directions
    """

    # If flow direction is out of the interior, set flow direction to -1
    if d4:
        change_top = np.where(flow_directions[1, :] == 4)[0]
        change_right = np.where(flow_directions[:, -2] == 1)[0]
        change_bottom = np.where(flow_directions[-2, :] == 2)[0]
        change_left = np.where(flow_directions[:, 1] == 3)[0]
    else:
        change_top = np.concatenate((np.where(flow_directions[1, :] == 1)[0],
                                    np.where(flow_directions[1, :] == 64)[0],
                                    np.where(flow_directions[1, :] == 128)[0]))
        change_right = np.concatenate((np.where(flow_directions[:, -2] == 1)[0],
                                      np.where(flow_directions[:, -2] == 2)[0],
                                      np.where(flow_directions[:, -2] == 4)[0]))
        change_bottom = np.concatenate((np.where(flow_directions[-2, :] == 4)[0],
                                       np.where(flow_directions[-2, :] == 8)[0],
                                       np.where(flow_directions[-2, :] == 16)[0]))
        change_left = np.concatenate((np.where(flow_directions[:, 1] == 16)[0],
                                     np.where(flow_directions[:, 1] == 32)[0],
                                     np.where(flow_directions[:, 1] == 64)[0]))

    flow_directions[1, change_top] = -1
    flow_directions[change_right, -2] = -1
    flow_directions[-2, change_bottom] = -1
    flow_directions[change_left, 1] = -1

    # This function does not return something, just change the input flow_directions


def get_flow_direction_indices(heights, step_size, rows, cols, d4):
    """
    For every coordinate specifies the next index it flows to. If no flow, the index is set as -1.
    All boundary nodes have a flow set to None, as there's not enough information to determine.
    :param heights: Heights of grid
    :param step_size: Length between grid points
    :param rows: Nodes in y-direction
    :param cols: Nodes in x-direction
    :param d4: Use the D4-method instead of D8
    :return flow_directions: Next node it flows to
    """

    if d4:
        flow_directions = get_flow_directions(heights, step_size, rows, cols, d4=True)
        remove_out_of_boundary_flow(flow_directions, d4=True)
    else:
        flow_directions = get_flow_directions(heights, step_size, rows, cols, d4=False)
        remove_out_of_boundary_flow(flow_directions, d4=False)

    # Copy flow directions, and write to that array
    flow_direction_indices = np.copy(flow_directions)

    if d4:
        values = [1, 2, 3, 4]
        translations = [1, cols, -1, -cols]
    else:
        values = [1, 2, 4, 8, 16, 32, 64, 128]
        translations = [-cols + 1, 1, cols + 1, cols, cols - 1, -1, -cols - 1, -cols]

    for ix in range(len(values)):
        coords = np.where(flow_directions == values[ix])
        if len(coords[0]) > 0:
            from_ix = coords[0] * cols + coords[1]
            to_ix = from_ix + translations[ix]
            flow_direction_indices[coords] = to_ix

    return flow_direction_indices


def map_2d_to_1d(coords, cols):
    """
    Map from a 2D-grid to a 1D-array
    :param coords: Coords in a tuple (coords_rows, coords_cols)
    :param cols: Nr of columns
    :return indices: Indices in the 1D-array
    """

    indices = coords[1] + coords[0] * cols

    return indices


def map_1d_to_2d(indices, cols):
    """
    Map from a 1D-array to a 2D-grid
    :param indices: Indices in the 1D-array
    :param cols: Number of columns in the 2D-grid
    :return rows, cols: Tuple containing the row and col indices
    """

    rows = np.divide(indices, cols)
    cols = (indices % cols)

    return rows, cols


def get_node_endpoints(downslope_neighbors):
    """
    Returns a 2d array specifying node endpoint for the coordinate
    :param downslope_neighbors: Downslope index for each coordinate
    :return terminal_nodes: The end point for each node
    """

    rows, cols = np.shape(downslope_neighbors)
    domain_boundary = get_domain_boundary_coords(cols, rows)

    terminal_nodes = np.empty((rows, cols), dtype=object)

    # Get all minima as starting points for stepwise algorithm
    minima = np.where(downslope_neighbors == -1)
    terminal_nodes[minima] = map_2d_to_1d(minima, cols)
    terminal_nodes[domain_boundary] = -2  # Finding terminal nodes is harder with None at the boundary

    num_inserted = len(minima[0])

    while num_inserted > 0:
        num_inserted, terminal_nodes = update_terminal_nodes(terminal_nodes, downslope_neighbors, cols)

    terminal_nodes[domain_boundary] = None

    return terminal_nodes


def update_terminal_nodes(terminal_nodes, downslope_neighbors, cols):
    """
    Help method for get_node_endpoints. Returns updated terminal nodes.
    :param terminal_nodes: Array specifying endpoint for each node
    :param downslope_neighbors: Downslope index for each coordinate
    :param cols: Nr of nodes in x-direction
    :return num_inserted, terminal_nodes: Nr of new coords with detected endpoint. 2d-array indicating endpoints
    """

    no_terminal_nodes = np.where(terminal_nodes < -2)  # Indices of all nodes without terminal nodes yet

    if len(no_terminal_nodes[0]) == 0:
        return 0, terminal_nodes
    next_nodes = downslope_neighbors[no_terminal_nodes]  # Check if these nodes are minima, or if they have endpoints

    # The next point is a minimum
    next_nodes = next_nodes.astype(int)  # Mapping for type object doesn't work
    are_minima = np.where(downslope_neighbors[map_1d_to_2d(next_nodes, cols)] == -1)[0]
    terminal_nodes[(no_terminal_nodes[0][are_minima], no_terminal_nodes[1][are_minima])] = next_nodes[are_minima]

    # The next point might have an end node
    undecided = np.setdiff1d(range(len(next_nodes)), are_minima)  # Might be nodes already assigned end points
    are_end_points = undecided[np.where(terminal_nodes[map_1d_to_2d(next_nodes[undecided], cols)] >= 0)[0]]
    terminal_nodes[(no_terminal_nodes[0][are_end_points], no_terminal_nodes[1][are_end_points])] = \
        terminal_nodes[map_1d_to_2d(next_nodes[are_end_points], cols)]

    num_inserted = len(are_minima) + len(are_end_points)

    return num_inserted, terminal_nodes


def get_local_watersheds(node_endpoints):

    endpoints = node_endpoints.flatten()
    unique, counts = np.unique(endpoints, return_counts=True)
    sorted_indices = np.argsort(endpoints)
    indices_to_endpoints = np.split(sorted_indices, np.cumsum(counts))[0:-1]

    local_watersheds = dict(zip(unique, indices_to_endpoints))
    del local_watersheds[None]  # All nodes with None as endpoint aren't of interest

    return local_watersheds


def map_1d_interior_to_2d_exterior(node_index, number_of_cols):

    r = node_index/number_of_cols + 1
    c = node_index % number_of_cols + 1
    row_col = zip(r, c)

    return row_col


def map_2d_exterior_to_1d_interior(coords, cols):

    indices = []
    for c in coords:
        ix = c[1] - 1 + (c[0] - 1) * cols
        indices.append(ix)

    return indices


def combine_minima(local_minima, rows, cols, d4):
    """
    Return the combined minima in the landscape as a list of arrays
    :param local_minima: 1D-array with indices of all minima
    :param rows: Nr of rows
    :param cols: Nr of columns
    :param d4: Use the D4-method instead of D8
    :return combined_minima: List of arrays containing the combined minima
    """

    if len(local_minima) == 1:  # One minimum returns list with one minimum combination
        return [local_minima]

    local_minima_2d = map_1d_to_2d(local_minima, cols)

    if d4:
        two = (local_minima_2d[0], local_minima_2d[1] + 1)
        eight = local_minima_2d[0] + 1, local_minima_2d[1]
        thirtytwo = local_minima_2d[0], local_minima_2d[1] - 1
        onetwentyeight = local_minima_2d[0] - 1, local_minima_2d[1]
        nbrs_to_minima = np.hstack((two, eight, thirtytwo, onetwentyeight))
    else:
        one = (local_minima_2d[0] - 1, local_minima_2d[1] + 1)
        two = (local_minima_2d[0], local_minima_2d[1] + 1)
        four = local_minima_2d[0] + 1, local_minima_2d[1] + 1
        eight = local_minima_2d[0] + 1, local_minima_2d[1]
        sixteen = local_minima_2d[0] + 1, local_minima_2d[1] - 1
        thirtytwo = local_minima_2d[0], local_minima_2d[1] - 1
        sixtyfour = local_minima_2d[0] - 1, local_minima_2d[1] - 1
        onetwentyeight = local_minima_2d[0] - 1, local_minima_2d[1]
        nbrs_to_minima = np.hstack((one, two, four, eight, sixteen, thirtytwo, sixtyfour, onetwentyeight))

    nbrs_to_minima_1d = map_2d_to_1d(nbrs_to_minima, cols)
    from_min = np.concatenate([local_minima for i in range(8)])

    # Only keep connections between minima
    nbrs_are_minima = np.where(np.in1d(nbrs_to_minima_1d, local_minima))[0]
    to_min = nbrs_to_minima_1d[nbrs_are_minima]
    from_min = from_min[nbrs_are_minima]
    data = np.ones(len(to_min), dtype=int)

    # Make connectivity matrix between pairs of minima
    conn = csr_matrix((data, (from_min, to_min)), shape=(rows*cols, rows*cols), dtype=int)
    n_components, labels = csgraph.connected_components(conn, directed=False)
    unique, counts = np.unique(labels, return_counts=True)

    sorted_indices = np.argsort(labels)

    nodes_in_comb_min = np.split(sorted_indices, np.cumsum(counts))[0:-1]

    combined_minima = [ws for ws in nodes_in_comb_min if len(ws) > 1]

    if len(combined_minima) == 0:
        combined_minima = [np.array([m]) for m in local_minima]
        return combined_minima
    else:  # There are only single minima, so no combinations are created
        already_located_minima = np.concatenate(combined_minima)
        remaining_minima = np.setdiff1d(local_minima, already_located_minima)
        [combined_minima.append(np.array([remaining_minima[i]])) for i in range(len(remaining_minima))]

    return combined_minima


def combine_watersheds(local_watersheds, combined_minima):
    """
    Combine all watersheds with adjacent minima, leave the rest as is
    :param local_watersheds: Watersheds leading to a minima
    :param combined_minima: Collection of adjacent minima
    :return watersheds: The combined watersheds
    """

    watersheds = []

    for i in range(len(combined_minima)):
        if len(combined_minima[i]) == 1:
            watersheds.append(local_watersheds[list(combined_minima[i])[0]])
        else:
            ws = np.concatenate(list((local_watersheds[i] for i in combined_minima[i])))
            watersheds.append(ws)

    return watersheds


def create_nbr_connectivity_matrix(flow_directions, nx, ny, d4):
    # Note: This is a version without 1 on the diagonal
    """
    Create a connectivity matrix between all nodes using the flow
    :param flow_directions: 2D-grid showing the flow
    :param nx: Number of cols
    :param ny: Number of rows
    :param d4: Use the D4-method instead of D8
    :return A: Returns a sparse adjacency matrix
    """

    # Start by removing the flow out of the boundary
    if d4:
        remove_out_of_boundary_flow(flow_directions, d4=True)
    else:
        remove_out_of_boundary_flow(flow_directions, d4=False)

    values = [1, 2, 4, 8, 16, 32, 64, 128]
    translations = [-nx + 1, 1, nx + 1, nx, nx - 1, -1, -nx - 1, -nx]
    from_indices = []
    to_indices = []
    total_nodes = nx * ny

    for ix in range(len(values)):
        coords = np.where(flow_directions == values[ix])
        if len(coords[0]) > 0:
            from_ix = coords[0] * nx + coords[1]
            to_ix = from_ix + translations[ix]
            from_indices.append(from_ix)
            to_indices.append(to_ix)

    rows = np.concatenate(from_indices)
    cols = np.concatenate(to_indices)
    data = np.ones(len(rows))

    adj_mat = csr_matrix((data, (rows, cols)), shape=(total_nodes, total_nodes))

    return adj_mat


def get_minima(adj_mat):
    """
    Returns the indices of the local minima
    :param adj_mat: Matrix showing where flow occurs
    :return minima: Indices of the minima
    """

    minima = np.where(np.diff(adj_mat.indptr) == 0)[0]

    return minima


def get_downslope_rivers(adj_mat):
    """
    Returns a matrix showing all downslope nodes for each node
    :param adj_mat: Matrix showing where flow occurs
    :return downslope_rivers: Sparse matrix with ones at downslope nodes
    """

    rows, cols = np.shape(adj_mat)
    changes = True
    id_matrix = identity(rows, dtype=int, format='csr')
    downslope_rivers = adj_mat + id_matrix  # Set diagonal to 1

    AA = adj_mat

    while changes:
        changes = False
        AA = csr_matrix.dot(AA, adj_mat)

        if AA.nnz > 0:
            changes = True
            downslope_rivers = AA + downslope_rivers

    return downslope_rivers


def get_row_and_col_from_indices(node_indices, number_of_cols):
    """
    Return (r, c) for all indices in node_indices.
    :param node_indices: Indices in the 1d-grid.
    :param number_of_cols: Number of columns in the 2d-grid.
    :return row_col: (r, c) for every index
    """

    row_col = np.empty((len(node_indices), 2), dtype=int)
    row_col[:, 0] = np.divide(node_indices, number_of_cols)
    row_col[:, 1] = node_indices % number_of_cols

    return row_col


def get_watersheds_with_combined_minima(combined_minima, local_watersheds):

    watersheds = []
    for c in combined_minima:
        watersheds.append(np.concatenate([local_watersheds[el] for el in c]))

    return watersheds


def get_boundary_pairs_in_watersheds(watersheds, nx, ny, d4):
    """
    Return all boundary pairs between all watersheds. If domain pairs should be excluded,
    remove comments at indicated places.
    :param watersheds: All watersheds of the domain.
    :param nx: Nr of nodes in x-direction
    :param ny: Nr of nodes in y-direction
    :param d4: Use the D4-method instead of D8
    :return boundary_pairs: List of lists where each list contain a tuple of two arrays
    """

    indices = np.arange(0, nx * ny, 1)
    if d4:
        nbrs = get_neighbor_indices(indices, nx, d4=True)
    else:
        nbrs = get_neighbor_indices(indices, nx, d4=False)

    # N.B: If boundary pairs to domain should be removed, include line below
    # domain_bnd_nodes = get_domain_boundary_indices(nx, ny)

    boundary_pairs = []

    for watershed in watersheds:

        watershed = np.sort(watershed)
        nbrs_for_ws = nbrs[watershed]
        nbrs_for_ws_1d = np.concatenate(nbrs_for_ws)

        # Find nodes not in the watershed which aren't at the domain boundary
        not_in_watershed_arr = np.in1d(nbrs_for_ws_1d, watershed, invert=True)

        # N.B: If boundary pairs to domain should be removed, include lines below
        # at_dom_boundary = np.in1d(nbrs_for_ws_1d, domain_bnd_nodes)
        # valid_nodes = np.where((not_in_watershed_arr - at_dom_boundary) == True)[0]

        # Pairs in from-to format
        if d4:
            repeat_from = np.repeat(watershed, 4)
        else:
            repeat_from = np.repeat(watershed, 8)
        from_indices = repeat_from[not_in_watershed_arr]
        to_indices = nbrs_for_ws_1d[not_in_watershed_arr]
        boundary_pairs_for_ws = [from_indices, to_indices]
        boundary_pairs.append(boundary_pairs_for_ws)

    return boundary_pairs


def get_boundary_pairs_for_specific_watersheds(specific_watersheds, nx, d4):
    """
    Only find boundary pairs for specified watersheds.
    :param specific_watersheds: Selection of watersheds
    :param nx: Number of nodes in x-direction
    :param d4: Use the D4-method instead of D8
    :return boundary_pairs: Boundary pairs for specified watersheds
    """

    boundary_pairs = []

    for watershed in specific_watersheds:

        if d4:
            nbrs = get_neighbor_indices(watershed, nx, d4=True)
        else:
            nbrs = get_neighbor_indices(watershed, nx, d4=False)
        nbrs_for_ws_1d = np.concatenate(nbrs)
        valid_nodes = np.in1d(nbrs_for_ws_1d, watershed, invert=True)

        # Pairs in from-to format
        if d4:
            repeat_from = np.repeat(watershed, 4)
        else:
            repeat_from = np.repeat(watershed, 8)
        from_indices = repeat_from[valid_nodes]
        to_indices = nbrs_for_ws_1d[valid_nodes]
        boundary_pairs_for_ws = [from_indices, to_indices]
        boundary_pairs.append(boundary_pairs_for_ws)

    return boundary_pairs


def get_possible_spill_pairs(heights, boundary_pairs):
    """
    Returns a list of lists where each list contains the possible spill pairs from one watershed to another
    :param heights: Heights of terrain
    :param boundary_pairs: Pairs between watershed boundaries
    :return spill_pairs: Possible spill pairs
    """

    rows, cols = np.shape(heights)
    heights = np.reshape(heights, rows * cols)
    heights_pairs = [heights[np.vstack((arr[0], arr[1]))] for arr in boundary_pairs]

    # Min(max elevation of each pair)
    min_of_max = [np.min(np.max(heights_pairs[i], axis=0)) for i in range(len(heights_pairs))]

    # If x -> y, both x and y have heights <= min_of_max
    indices = [np.where(np.logical_and(heights_pairs[i][0] <= min_of_max[i], heights_pairs[i][1] <= min_of_max[i]))[0]
               for i in range(len(heights_pairs))]

    spill_pairs = [[boundary_pairs[i][0][indices[i]], boundary_pairs[i][1][indices[i]]] for i in range(len(indices))]

    return spill_pairs


def get_steepest_spill_pair(heights, spill_pairs, d4):
    """
    Return a list of tuples where each tuple is the spill pair for each watershed
    :param heights: Heights of terrain
    :param spill_pairs: List of lists. Each list contains two arrays in from-to format
    :return steepest_spill_pairs: Set containing the steepest spill pairs
    """

    rows, cols = np.shape(heights)
    heights = np.reshape(heights, rows * cols)
    steepest_spill_pairs = [None] * len(spill_pairs)

    for i in range(len(spill_pairs)):
        diff = abs(spill_pairs[i][0] - spill_pairs[i][1])
        derivatives = np.array([None] * len(spill_pairs[i][0]), dtype=object)

        card_indices = np.where(np.logical_or(diff == 1, diff == cols))[0]
        diag_indices = np.setdiff1d(np.arange(0, len(spill_pairs[i][0]), 1), card_indices)
        card_der = (heights[spill_pairs[i][0][card_indices]] - heights[spill_pairs[i][1][card_indices]])/10.0
        diag_der = (heights[spill_pairs[i][0][diag_indices]] - heights[spill_pairs[i][1][diag_indices]])/math.sqrt(200)
        derivatives[card_indices] = card_der
        derivatives[diag_indices] = diag_der
        max_index = np.argmax(derivatives)
        steepest_spill_pairs[i] = (spill_pairs[i][0][max_index], spill_pairs[i][1][max_index])

    return set(steepest_spill_pairs)


def map_nodes_to_watersheds(watersheds, rows, cols):
    """
    Map between node indices and watershed number
    :param watersheds: List of arrays containing watersheds
    :param rows: Nr of rows
    :param cols: Nr of columns
    :return mapping_nodes_to_watersheds: Array where index gives watershed nr
    """

    mapping_nodes_to_watersheds = np.ones(rows * cols, dtype=int) * -1

    for i in range(len(watersheds)):
        mapping_nodes_to_watersheds[watersheds[i]] = i

    return mapping_nodes_to_watersheds


def merge_watersheds_flowing_into_each_other(watersheds, steepest_spill_pairs, rows, cols):

    map_node_to_ws = map_nodes_to_watersheds(watersheds, rows, cols)

    # Dictionary used for removing merged spill_pairs
    d = {}
    for s_p in steepest_spill_pairs:
        key = (map_node_to_ws[s_p[0]], map_node_to_ws[s_p[1]])
        value = s_p
        d[key] = value

    # Use set operations to find pairs of watersheds spilling to each other
    temp = set([(map_node_to_ws[el[0]], map_node_to_ws[el[1]]) for el in steepest_spill_pairs])
    temp_rev = set([(map_node_to_ws[el[1]], map_node_to_ws[el[0]]) for el in steepest_spill_pairs])
    pairs_to_each_other = temp.intersection(temp_rev)

    # Remove (y, x) when (x, y) is in the set
    merge_pairs = set(tuple(sorted(x)) for x in pairs_to_each_other)

    # Create the new list of watersheds
    merged_watersheds = [np.concatenate((watersheds[el[0]], watersheds[el[1]])) for el in merge_pairs]

    merged_indices = np.unique(list(merge_pairs))
    if len(pairs_to_each_other) > 0:
        removed_spill_pairs = set(itemgetter(*pairs_to_each_other)(d))
    else:
        removed_spill_pairs = {}

    return merged_watersheds, removed_spill_pairs, merged_indices


def combine_watersheds_spilling_into_each_other(watersheds, heights, d4):
    """
    Iterative process to combine all watersheds spilling into each other
    :param watersheds: Different areas flowing to the same area
    :param heights: Heights of terrain
    :param d4: Use the D4-method instead of D8
    :return watersheds: New collection of watersheds where some have been merged
    """

    ny, nx = np.shape(heights)

    remaining_spill_pairs = {}
    merged_watersheds = watersheds
    steepest_spill_pairs = None
    it = 0

    while len(merged_watersheds) > 0:
        print it

        # Find spill pairs for given watersheds
        boundary_pairs = get_boundary_pairs_for_specific_watersheds(merged_watersheds, nx, d4)
        spill_pairs = get_possible_spill_pairs(heights, boundary_pairs)
        steepest_spill_pairs = get_steepest_spill_pair(heights, spill_pairs, d4)

        # Add the new spill pairs to the unaltered ones
        steepest_spill_pairs = steepest_spill_pairs.union(remaining_spill_pairs)

        # Merge watersheds spilling into each other
        merged_watersheds, removed_spill_pairs, merged_indices = merge_watersheds_flowing_into_each_other(
            watersheds, steepest_spill_pairs, ny, nx)
        remaining_spill_pairs = steepest_spill_pairs.difference(removed_spill_pairs)

        # Remove the merged watersheds from watersheds. Add the new ones to the end
        watersheds = [watersheds[i] for i in range(len(watersheds)) if i not in merged_indices]
        watersheds.extend(merged_watersheds)

        it += 1
        if len(merged_watersheds) == 0:  # Remove cycles at last iteration
            merged_watersheds, removed_spill_pairs, merged_indices = remove_cycles(
                watersheds, steepest_spill_pairs, ny, nx)
            remaining_spill_pairs = steepest_spill_pairs.difference(removed_spill_pairs)
            watersheds = [watersheds[i] for i in range(len(watersheds)) if i not in merged_indices]
            watersheds.extend(merged_watersheds)

    # Order the steepest spill pairs
    mapping = map_nodes_to_watersheds(watersheds, ny, nx)
    if steepest_spill_pairs:
        steepest_spill_pairs = list(steepest_spill_pairs)
        order = np.argsort([mapping[s[0]] for s in steepest_spill_pairs])
        steepest_spill_pairs = [steepest_spill_pairs[el] for el in order]

    return watersheds, steepest_spill_pairs


def remove_cycles(watersheds, steepest, ny, nx):
    # Remove cycles by combining the watersheds involved in a cycle

    steepest = list(steepest)
    mapping = map_nodes_to_watersheds(watersheds, ny, nx)

    # Only spill_pairs going from a ws to another ws, no paths between ws and boundary
    spill_pairs = [(mapping[steepest[i][0]], mapping[steepest[i][1]]) for i in range(len(steepest))
                   if (mapping[steepest[i][0]] != -1 and mapping[steepest[i][1]] != -1)]

    DG = networkx.DiGraph()
    DG.add_edges_from(spill_pairs)

    # Remove cycles
    cycles = sorted(networkx.simple_cycles(DG))

    merged_indices = sorted([x for l in cycles for x in l])
    ws_not_being_merged = np.setdiff1d(np.arange(0, len(watersheds), 1), merged_indices)
    merged_watersheds = [np.concatenate([watersheds[el] for el in c]) for c in cycles]

    # Remove the no longer valid spill pairs
    d = {}
    for s_p in steepest:
        key = (mapping[s_p[0]], mapping[s_p[1]])
        value = s_p
        d[key] = value

    removed_spill_pairs = set([d[el] for el in spill_pairs if el[0] in merged_indices])

    return merged_watersheds, removed_spill_pairs, merged_indices


def get_spill_heights(watersheds, heights, steepest_spill_pairs):
    """
    Returns the height of spilling
    :param watersheds: All watersheds for landscape
    :param heights: Heights of landscape
    :param steepest_spill_pairs: One pair for each watershed, (from_node, to_node)
    :return spill_heights: The spill height for each watershed
    """

    if not steepest_spill_pairs:
        return None
    r, c = np.shape(heights)
    mapping = map_nodes_to_watersheds(watersheds, r, c)

    ws_pair_heights = [((mapping[el[0]], mapping[el[1]]), max(heights[map_1d_to_2d(el[0], c)], heights[map_1d_to_2d(el[1], c)]))
                       for el in steepest_spill_pairs]
    ws_pair_heights = sorted(ws_pair_heights)
    spill_heights = np.asarray([el[1] for el in ws_pair_heights])

    return spill_heights


def get_size_of_traps(watersheds, heights, spill_heights):
    """
    Returns the size of the traps for each watershed, i.e. the number of cells below the spill height
    :param watersheds: All watersheds for landscape
    :param heights: Heights of landscape
    :param spill_heights: The spill height for each watershed
    :return size_of_traps: Number of elements below spill height for each watershed
    """

    r, c = np.shape(heights)
    size_of_traps = np.asarray([np.sum(heights[map_1d_to_2d(watersheds[i], c)] <= spill_heights[i])
                                for i in range(len(spill_heights))])

    return size_of_traps


def remap_steepest_spill_pairs(watersheds, steepest_spill_pairs, rows, cols):

    mapping = map_nodes_to_watersheds(watersheds, rows, cols)
    steepest_spill_pairs = [el for el in steepest_spill_pairs
                            if np.logical_and(mapping[el[0]] != -1, mapping[el[0]] != mapping[el[1]])]

    return steepest_spill_pairs


def get_threshold_traps(watersheds, size_of_traps, threshold, heights):

    r, c = np.shape(heights)

    keep_indices = np.where(size_of_traps > threshold)[0]

    # The traps of the watershed above the threshold
    traps = []
    for i in keep_indices:
        ws = watersheds[i]
        ws_2d = map_1d_to_2d(ws, c)
        trap = ws[np.where(heights[ws_2d] <= size_of_traps[i])[0]]
        traps.append(trap)

    return traps


def get_all_traps(watersheds, heights, spill_heights):
    """
    Get all traps in a watershed given watersheds, landscape heights and spill heights of watersheds
    :param watersheds: All watersheds in landscape
    :param heights: Heights of landscape
    :param spill_heights: Spill height in each watershed
    :return traps: All traps
    :return size_of_traps: Size of each trap
    """

    r, c = np.shape(heights)

    traps = []
    for i in range(len(watersheds)):
        ws = watersheds[i]
        ws_2d = map_1d_to_2d(ws, c)
        trap = ws[np.where(heights[ws_2d] <= spill_heights[i])[0]]
        traps.append(trap)

    size_of_traps = np.asarray([len(t) for t in traps])

    return traps, size_of_traps


def remove_watersheds_below_threshold(watersheds, conn_mat, size_of_traps, threshold_size):

    remove_indices = np.where(size_of_traps < threshold_size)[0]
    it = 0

    for i in range(len(remove_indices)):
        remove_ix = remove_indices[i]
        downslope_ws = conn_mat[remove_ix, :].nonzero()[1]  # Only one
        upslope_ws = conn_mat[:, remove_ix].nonzero()[0]  # Might be several
        a = watersheds[remove_ix]
        if len(downslope_ws) == 0 and len(upslope_ws) == 0:  # Loner watershed
            del watersheds[remove_ix]
            remove_indices[remove_indices > remove_ix] -= 1
            conn_mat = remove_ix_from_conn_mat(conn_mat, remove_ix)
            it += 1
        else:
            if len(downslope_ws):  # Merge with downslope
                watersheds[downslope_ws] = np.concatenate((watersheds[downslope_ws], watersheds[remove_ix]))
            del watersheds[remove_ix]
            remove_indices[remove_indices > remove_ix] -= 1
            conn_mat = remove_ix_from_conn_mat(conn_mat, remove_ix)
            it += 1

    return conn_mat, watersheds


def remove_ix_from_conn_mat(conn_mat, ix):
    """
    Remove indicated index from connectivity matrix. Reroute all connections.
    :param conn_mat: Connectivity between watersheds
    :param ix: Watershed below threshold to be removed
    :return conn_mat: The new connectivity matrix with index removed
    """

    nr_of_watersheds = conn_mat.shape[0]
    keep_indices = np.concatenate((np.arange(0, ix, 1, dtype=int), np.arange(ix+1, nr_of_watersheds, 1, dtype=int)))
    downslope_indices = conn_mat[ix, :].nonzero()[1]  # Only one
    upslope_indices = conn_mat[:, ix].nonzero()[0]  # Might be several

    # Reroute before remove
    if len(downslope_indices) and len(upslope_indices):
        conn_mat[upslope_indices, downslope_indices] = 1

    conn_mat = conn_mat[keep_indices, :]  # Keep rows
    conn_mat = conn_mat[:, keep_indices]  # Keep cols

    return conn_mat


def merge_watersheds(watersheds, steepest, nx, ny):

    mapping = map_nodes_to_watersheds(watersheds, ny, nx)

    # Only spill_pairs going from a ws to another ws, no paths between ws and boundary
    spill_pairs = [(mapping[steepest[i][0]], mapping[steepest[i][1]]) for i in range(len(steepest))
                   if (mapping[steepest[i][0]] != -1 and mapping[steepest[i][1]] != -1)]

    DG = networkx.DiGraph()
    DG.add_edges_from(spill_pairs)

    G = DG.to_undirected()
    watershed_indices = sorted(networkx.connected_components(G))

    ws_being_merged = sorted([x for l in watershed_indices for x in l])
    ws_not_being_merged = np.setdiff1d(np.arange(0, len(watersheds), 1), ws_being_merged)
    merged_watersheds = [np.concatenate([watersheds[el] for el in ws_set]) for ws_set in watershed_indices]

    not_merged_watersheds = [watersheds[el] for el in ws_not_being_merged]
    merged_watersheds.extend(not_merged_watersheds)

    watersheds = merged_watersheds

    return watersheds


def create_watershed_conn_matrix(watersheds, steepest_spill_pairs, rows, cols):
    """
    Returns a connectivity matrix in csr_matrix format. This shows which watersheds are connected.
    :param watersheds: List of arrays where each array contains node indices for the watershed.
    :param steepest_spill_pairs: List of pairs where each pair is a spill pair between two node indices.
    :param rows: Nr of rows
    :param cols: Nr of cols
    :return conn_mat: The connectivity matrix showing connections between watersheds.
    """

    map_ix_to_ws = map_nodes_to_watersheds(watersheds, rows, cols)
    steepest_pairs_ws_nr = [(map_ix_to_ws[p[0]], map_ix_to_ws[p[1]]) for p in steepest_spill_pairs
                            if map_ix_to_ws[p[1]] != -1]
    from_ws = [p[0] for p in steepest_pairs_ws_nr]
    to_ws = [p[1] for p in steepest_pairs_ws_nr]

    nr_of_watersheds = len(watersheds)

    row_indices = from_ws
    col_indices = to_ws
    data = np.ones(len(row_indices))

    conn_mat = csr_matrix((data, (row_indices, col_indices)), shape=(nr_of_watersheds, nr_of_watersheds))

    return conn_mat


def calculate_watersheds(heights, dim_x, dim_y, step_size, d4):
    """
    Given information about grid and heights, the watersheds are calculated. Information about spill points are used to
    merge watersheds spilling into each other.
    :param heights: The elevations for the grid points. The landscape must have single-cell depressions filled!
    :param dim_x: Size of grid in x-dimension
    :param dim_y: Size of grid in y-dimension
    :param d4: Use the D4-method instead of D8
    :param step_size: Length between points in one dimension
    :return:
    """

    flow_directions = get_flow_direction_indices(heights, step_size, dim_y, dim_x, d4)
    node_endpoints = get_node_endpoints(flow_directions)
    local_watersheds = get_local_watersheds(node_endpoints)
    local_minima = np.asarray(local_watersheds.keys())
    combined_minima = combine_minima(local_minima, dim_y, dim_x, d4)
    watersheds = combine_watersheds(local_watersheds, combined_minima)
    watersheds, steepest_spill_pairs = combine_watersheds_spilling_into_each_other(watersheds, heights, d4)

    return watersheds, steepest_spill_pairs, flow_directions


def calculate_thresholded_watersheds(watersheds, steepest_spill_pairs, landscape, threshold):
    """
    Returns the thresholded watersheds
    :param watersheds: All watersheds in the domain
    :param steepest_spill_pairs: The spill pairs between all watersheds
    :param landscape: Landscape object
    :param threshold: The algorithm removes or merges all watersheds with traps below the threshold
    :return new_watersheds: The thresholded watersheds
    """

    conn_mat = create_watershed_conn_matrix(watersheds, steepest_spill_pairs, landscape.ny, landscape.nx)
    spill_heights = get_spill_heights(watersheds, landscape.heights, steepest_spill_pairs)
    traps, size_of_traps = get_all_traps(watersheds, landscape.heights, spill_heights)
    new_conn_mat, new_watersheds = remove_watersheds_below_threshold(watersheds, conn_mat, size_of_traps, threshold)

    return new_watersheds


def make_landscape_depressionless(watersheds, steepest_spill_pairs, landscape):
    """
    Makes the landscape depressionless by filling the traps to the spill heights. It is important that watersheds
    spilling into each other have been combined. The result is a monotonically decreasing landscape.
    :param watersheds: All watersheds in the domain
    :param steepest_spill_pairs: The spill pairs for all watersheds
    :param landscape: Landscape object
    :return: Nothing. It only modifies landscape.heights.
    """

    spill_heights = get_spill_heights(watersheds, landscape.heights, steepest_spill_pairs)
    traps, size_of_traps = get_all_traps(watersheds, landscape.heights, spill_heights)

    for i in range(len(traps)):
        landscape.heights[map_1d_to_2d(np.asarray(traps[i]), landscape.nx)] = spill_heights[i]


def make_landscape_depressionless_no_landscape_input(watersheds, steepest_spill_pairs, heights, nx):
    """
    Makes the landscape depressionless by filling the traps to the spill heights. It is important that watersheds
    spilling into each other have been combined. The result is a monotonically decreasing landscape.
    :param watersheds: All watersheds in the domain
    :param steepest_spill_pairs: The spill pairs for all watersheds
    :param heights: Heights of landscape
    :param ny: Nr of rows
    :return: Nothing. It only modifies landscape.heights.
    """

    spill_heights = get_spill_heights(watersheds, heights, steepest_spill_pairs)
    traps, size_of_traps = get_all_traps(watersheds, heights, spill_heights)

    for i in range(len(traps)):
        heights[map_1d_to_2d(np.asarray(traps[i]), nx)] = spill_heights[i]


def make_depressionless(heights, step_size, d4):
    """
    Given only heights and step_size, calculate the depressionless landscape
    :param heights: Heights of domain
    :param step_size: Step size between grid points, assume regular grid
    :param d4: Use the D4-method instead of D8
    :return heights: The new heights with depressions filled
    """

    ny, nx = np.shape(heights)
    fill_single_cell_depressions(heights, ny, nx)
    flow_directions = get_flow_direction_indices(heights, step_size, ny, nx, d4)
    node_endpoints = get_node_endpoints(flow_directions)
    local_watersheds = get_local_watersheds(node_endpoints)
    local_minima = np.asarray(local_watersheds.keys())
    combined_minima = combine_minima(local_minima, ny, nx, d4)
    watersheds = combine_watersheds(local_watersheds, combined_minima)
    watersheds, steepest_spill_pairs = combine_watersheds_spilling_into_each_other(watersheds, heights, d4)

    spill_heights = get_spill_heights(watersheds, heights, steepest_spill_pairs)
    traps, size_of_traps = get_all_traps(watersheds, heights, spill_heights)

    for i in range(len(traps)):
        heights[map_1d_to_2d(np.asarray(traps[i]), nx)] = spill_heights[i]

    return heights


def map_two_indices_to_flow_direction(ix_one, ix_two, cols):
    """
    Map two 1d-indices ix_one -> ix_two to the flow direction
    :param ix_one: From index
    :param ix_two: To index
    :param cols: Nr of columns in grid
    :return direction: One of the flow directions
    """

    flow_directions = np.array([1, 2, 4, 8, 16, 32, 64, 128])
    nbr_indices = get_neighbor_indices(np.array([ix_one]), cols, d4=False)
    direction = flow_directions[np.where(nbr_indices == ix_two)[1]]

    return direction
