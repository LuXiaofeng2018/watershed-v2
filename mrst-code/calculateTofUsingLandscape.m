%% Calculate time-of-flight using DEM

% From pre-processing: if a trap is spilling over into a cell at equal
% height, add that cell to the trap

% Load necessary data and compute geometry
load('watershed.mat');
load('heights.mat');
load('traps.mat');
load('flowDirections.mat')

[nRows, nCols] = size(heights);
totalCells = nRows * nCols;

% Pre-process input data
heights = rot90(heights, -1);  % Fix 1d-indexing
fd = rot90(flowDirections, -1);  % Fix 1d-indexing
ws = util.mapCoordsToIndices(watershed', nCols, nRows);

% Create coarse grid and set heights
CG = util.createCoarseGrid(ws, heights, traps, nrOfTraps);
CG.cells.z = util.setHeightsCoarseGrid(CG, heights, trapHeights, nrOfTraps);

figure();
newplot
plotGrid(CG,'FaceColor',[0.95 0.95 0.95]); axis off;
plotCellData(CG,(1:CG.cells.num)','EdgeColor','w','EdgeAlpha',.2);
plotFaces(CG,(1:CG.faces.num)', 'FaceColor','none','LineWidth',2);
colormap(.5*(colorcube(20) + ones(20,3))); axis off


%% Show cell/block indices
% In its basic form, the structure onl347y represents topological information
% that specifies the relationship betwflow_directionseen blocks and block interfaces, etc.
% The structure also contains information of the underlying fine grid. Let
% us start by plotting cell/block indices
tg = text(CG.parent.cells.centroids(:,1), CG.parent.cells.centroids(:,2), ...
   num2str((1:CG.parent.cells.num)'),'FontSize',8, 'HorizontalAlignment','center');
tcg = text(CG.cells.centroids(:,1), CG.cells.centroids(:,2), ...
   num2str((1:CG.cells.num)'),'FontSize',16, 'HorizontalAlignment','center');
axis off;
set(tcg,'BackgroundColor','w','EdgeColor','none');
colormap(.5*jet+.5*ones(size(jet)));

%% Show face indices of fine/coarse grids
delete([tg; tcg]);
tg = text(CG.parent.faces.centroids(:,1), CG.parent.faces.centroids(:,2), ...
   num2str((1:CG.parent.faces.num)'),'FontSize',7, 'HorizontalAlignment','center');
tcg = text(CG.faces.centroids(:,1), CG.faces.centroids(:,2), ...
   num2str((1:CG.faces.num)'),'FontSize',12, 'HorizontalAlignment','center');
set(tcg,'BackgroundColor','w','EdgeColor','none');

%% Add flux field, state, rock and source


CG.cells.fd = util.getFlowDirections(CG, fd, nrOfTraps);

flux = util.setFlux(CG, nrOfTraps);

%flux = zeros(CG.faces.num, 1);
%indWithFlux = all(CG.faces.neighbors > 0, 2);
%N = CG.faces.neighbors;
%flux(indWithFlux) = (CG.cells.z(CG.faces.neighbors(indWithFlux, 1)) - CG.cells.z(CG.faces.neighbors(indWithFlux, 2)));

state = struct('flux', flux);
rock = struct('poro', ones(CG.cells.num, 1));

% srcIx = map(util.mapCoordsToIndices(source, nCols, nRows));
src = addSource([], 200, -10);

%% Plot the watershed cells
newplot
plotGrid(CG,'FaceColor',[0.95 0.95 0.95]); axis off;

%% Perform time of flight computation
max_i = 0;
max_nonzero = 0;
max_time = 100;

tof = computeTimeOfFlight(state, CG, rock, 'src', src, ...
   'maxTOF', max_time, 'reverse', true);

clf,plotCellData(CG,tof);