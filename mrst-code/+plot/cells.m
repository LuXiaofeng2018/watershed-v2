function [] = cells(CG)
%CELLS Plots the grid structure of CG in two forms. 1. Cells, cell
%indices and traps. 2. Cell indices and face indices.
%   CELLS(CG) plots CG as both cell indices and faces, and the cells and
%   the trap cells in the grid.

phi = 1;
scaleFluxes = true;
[CG, ~] = calculateTof(phi, scaleFluxes);

% Colors
scale = 255;
blueBrewer = [140, 160, 203] ./ scale;
greenBrewer = [102, 194, 165] ./ scale;
blackNew = [eps, 0, 0];
whiteNew = [1 - eps, 1, 1];

%% Show cell/block indices and face indices of fine grid
% In its basic form, the structure only represents topological information
% that specifies the relationship between blocks and block interfaces, etc.
% The structure also contains information of the underlying fine gr id. Let
% us start by plotting cell/block indices
f = figure('position', [100, 100, 1000, 1000]);
figure(f);
plotGrid(CG.parent, 'FaceColor', greenBrewer);
axis off

textCells = text(CG.parent.cells.centroids(:,1), CG.parent.cells.centroids(:,2), ...
   num2str((1:CG.parent.cells.num)'),'FontSize',24, 'HorizontalAlignment','center');
set(textCells,'BackgroundColor','w','EdgeColor','None');

textFaces = text(CG.parent.faces.centroids(:,1), CG.parent.faces.centroids(:,2), ...
   num2str((1:CG.parent.faces.num)'),'FontSize',16, 'HorizontalAlignment','center', 'Color', whiteNew);
set(textFaces,'BackgroundColor',blackNew,'EdgeColor','none');

print(f, '-depsc', 'gridStructure.eps')


%% Show cell/block indices and show face indices of coarse grid
% In its basic form, the structure only represents topological information
% that specifies the relationship between blocks and block interfaces, etc.
% The structure also contains information of the underlying fine gr id. Let
% us start by plotting cell/block indices

f = figure('position', [100, 100, 1000, 1000]);
figure(f);

colorIndices = zeros(CG.cells.num, 1);
colorIndices(CG.cells.num - nrOfTraps + 1:end) = 1;
colors = zeros(2, 3);
colors(1, :) = greenBrewer;
colors(2, :) = blueBrewer;
plotGrid(CG, find(colorIndices == 0), 'faceColor', colors(1, :));
plotGrid(CG, find(colorIndices), 'faceColor', colors(2, :));

axis off

textCells = text(CG.cells.centroids(:,1), CG.cells.centroids(:,2), ...
   num2str((1:CG.cells.num)'),'FontSize',24, 'HorizontalAlignment','center');
set(textCells,'BackgroundColor','w','EdgeColor','none');

%textFaces = text(CG.faces.centroids(:,1), CG.faces.centroids(:,2), ...
%   num2str((1:CG.faces.num)'),'FontSize',16, 'HorizontalAlignment','center', 'Color', whiteNew);
%set(textFaces,'BackgroundColor',blackNew,'EdgeColor','none');


print(f, '-dsvg', 'coarseGridStructure.svg')

end
