from lib import util, river_analysis, load_data, plot
import cPickle as pickle

"""
Calculates the accumulated flow for each node in the landscape. A node's number is the number of upslope nodes it has.
"""

saved_files = '/home/anderovo/Dropbox/watershedLargeFiles/'
file_name = saved_files + 'anders_hoh.tiff'

landscape = load_data.get_smallest_test_landscape_tyrifjorden(file_name)
landscape.heights = util.fill_single_cell_depressions(landscape.heights, landscape.ny, landscape.nx)
watersheds, steepest, flow_dir = util.calculate_watersheds(landscape.heights, landscape.nx, landscape.ny, landscape.step_size)
spill_heights = util.get_spill_heights(watersheds, landscape.heights, steepest)
traps, size_of_traps = util.get_all_traps(watersheds, landscape.heights, spill_heights)

# Increase heights of traps and recalculate flow. Remove flow from some indices in traps.
util.make_landscape_depressionless(watersheds, steepest, landscape)
flow = util.get_flow_direction_indices(landscape.heights, landscape.step_size, landscape.ny, landscape.nx)
for i in range(len(traps)):
    trap_in_2d = util.map_1d_to_2d(traps[i], landscape.nx)
    flow[trap_in_2d] = -1

node_conn_mat = util.make_sparse_node_conn_matrix(flow, landscape.ny, landscape.nx)
upslope_cells = river_analysis.calculate_nr_of_upslope_cells(node_conn_mat, landscape.ny, landscape.nx, traps, steepest)

# upslope_cells = pickle.load(open(saved_files + 'upslopeCells.pkl', 'rb'))
# pickle.dump(upslope_cells, open('upslopeCells.pkl', 'wb'))
plot.plot_accumulated_flow(upslope_cells)
# plot.plot_accumulated_flow_above_threshold(upslope_cells)

