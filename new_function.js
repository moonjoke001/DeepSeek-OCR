        // 解析带坐标的 OCR 结果，重建表格结构（v3 - 基于坐标范围计算 rowspan/colspan）
        function parseCoordinateOCR(text) {
            const lines = text.split('\n').filter(l => l.trim());
            const items = [];
            
            // 解析每行，提取文本和坐标
            for (const line of lines) {
                const match = line.match(/^(.+?)\[\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]\]$/);
                if (match) {
                    const x1 = parseInt(match[2]);
                    const y1 = parseInt(match[3]);
                    const x2 = parseInt(match[4]);
                    const y2 = parseInt(match[5]);
                    items.push({
                        text: match[1].trim(),
                        x1, y1, x2, y2,
                        width: x2 - x1,
                        height: y2 - y1
                    });
                }
            }
            
            if (items.length === 0) return null;
            
            // 1. 收集所有 Y 坐标（上下边界）来确定行边界
            const allYCoords = [];
            items.forEach(item => {
                allYCoords.push(item.y1);
                allYCoords.push(item.y2);
            });
            const uniqueY = [...new Set(allYCoords)].sort((a, b) => a - b);
            
            // 计算典型行高（用于聚类）
            const heights = items.map(i => i.height).sort((a, b) => a - b);
            const medianHeight = heights[Math.floor(heights.length / 2)] || 30;
            const rowTolerance = medianHeight * 0.4;
            
            // 聚类 Y 坐标得到行边界
            const rowBoundaries = clusterPositions(uniqueY, rowTolerance);
            
            // 2. 收集所有 X 坐标来确定列边界
            const allXCoords = [];
            items.forEach(item => {
                allXCoords.push(item.x1);
                allXCoords.push(item.x2);
            });
            const uniqueX = [...new Set(allXCoords)].sort((a, b) => a - b);
            
            const widths = items.map(i => i.width).sort((a, b) => a - b);
            const medianWidth = widths[Math.floor(widths.length / 2)] || 50;
            const colTolerance = medianWidth * 0.3;
            
            const colBoundaries = clusterPositions(uniqueX, colTolerance);
            
            // 3. 计算每个单元格跨越的行和列
            const cellsWithSpan = items.map(item => {
                // 找到起始行和结束行
                const startRow = findBoundaryIndex(rowBoundaries, item.y1, rowTolerance);
                const endRow = findBoundaryIndex(rowBoundaries, item.y2, rowTolerance);
                
                // 找到起始列和结束列
                const startCol = findBoundaryIndex(colBoundaries, item.x1, colTolerance);
                const endCol = findBoundaryIndex(colBoundaries, item.x2, colTolerance);
                
                // 计算 rowspan 和 colspan
                let rowspan = Math.max(1, endRow - startRow);
                let colspan = Math.max(1, endCol - startCol);
                
                return { ...item, startRow, endRow, startCol, endCol, rowspan, colspan };
            });
            
            // 4. 确定网格大小
            const numRows = Math.max(...cellsWithSpan.map(c => c.endRow), rowBoundaries.length - 1);
            const numCols = Math.max(...cellsWithSpan.map(c => c.endCol), colBoundaries.length - 1);
            
            // 5. 构建网格（跟踪哪些单元格被占用）
            const occupied = Array(numRows).fill(null).map(() => Array(numCols).fill(false));
            const grid = Array(numRows).fill(null).map(() => 
                Array(numCols).fill(null).map(() => ({ text: '', rowspan: 1, colspan: 1, skip: false, isHeader: false }))
            );
            
            // 按位置排序（从上到下，从左到右）
            cellsWithSpan.sort((a, b) => a.y1 - b.y1 || a.x1 - b.x1);
            
            // 6. 放置单元格
            for (const cell of cellsWithSpan) {
                const r = cell.startRow;
                const c = cell.startCol;
                
                if (r < 0 || r >= numRows || c < 0 || c >= numCols) continue;
                if (occupied[r][c]) continue;
                
                // 设置单元格内容
                grid[r][c].text = cell.text;
                grid[r][c].rowspan = cell.rowspan;
                grid[r][c].colspan = cell.colspan;
                
                // 标记占用的单元格
                for (let dr = 0; dr < cell.rowspan && r + dr < numRows; dr++) {
                    for (let dc = 0; dc < cell.colspan && c + dc < numCols; dc++) {
                        occupied[r + dr][c + dc] = true;
                        if (dr > 0 || dc > 0) {
                            grid[r + dr][c + dc].skip = true;
                        }
                    }
                }
            }
            
            // 7. 过滤空行
            const finalGrid = [];
            for (let r = 0; r < numRows; r++) {
                const row = grid[r];
                const hasContent = row.some(cell => cell.text && !cell.skip);
                const isPartOfMerge = row.some(cell => cell.skip);
                if (hasContent || isPartOfMerge) {
                    finalGrid.push(row);
                }
            }
            
            // 8. 检测表头行
            let headerRows = 0;
            for (let r = 0; r < Math.min(4, finalGrid.length); r++) {
                const row = finalGrid[r];
                const hasColspan = row.some(c => c.colspan > 1 && !c.skip);
                const hasContent = row.filter(c => c.text && !c.skip).length > 0;
                
                if (hasColspan || (r < 2 && hasContent)) {
                    headerRows = r + 1;
                    row.forEach(c => { if (!c.skip) c.isHeader = true; });
                }
            }
            
            return { rows: finalGrid, colCount: numCols, headerRows };
        }
        
        // 找到坐标对应的边界索引
        function findBoundaryIndex(boundaries, value, tolerance) {
            for (let i = 0; i < boundaries.length; i++) {
                if (Math.abs(boundaries[i] - value) <= tolerance) {
                    return i;
                }
            }
            // 如果没找到精确匹配，找最近的
            let minDist = Infinity, minIdx = 0;
            for (let i = 0; i < boundaries.length; i++) {
                const dist = Math.abs(boundaries[i] - value);
                if (dist < minDist) {
                    minDist = dist;
                    minIdx = i;
                }
            }
            return minIdx;
        }
        
