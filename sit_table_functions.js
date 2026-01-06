        function renderMarkdownTable(rows, hasHeader) {
            if (rows.length === 0) return '';
            
            // 解析所有行，保留空单元格
            const parsedRows = rows.map(row => {
                // 去掉首尾的 |，然后按 | 分割
                let trimmed = row.trim();
                if (trimmed.startsWith('|')) trimmed = trimmed.substring(1);
                if (trimmed.endsWith('|')) trimmed = trimmed.slice(0, -1);
                return trimmed.split('|').map(c => c.trim());
            });
            
            // 确定列数（取最大列数）
            const colCount = Math.max(...parsedRows.map(r => r.length));
            
            // 检测是否是 SIT 性能测试表（通过关键词检测）
            const isSITTable = parsedRows.some(row => 
                row.some(cell => /性能指标|并发|响应时间|吞吐率|TPS/.test(cell))
            );
            
            if (isSITTable && colCount >= 7) {
                return renderSITPerformanceTable(parsedRows, colCount);
            }
            
            // 普通表格渲染
            let html = '<div class="table-wrapper"><table>';
            parsedRows.forEach((cells, idx) => {
                const isHeader = hasHeader && idx === 0;
                const tag = isHeader ? 'th' : 'td';
                html += '<tr>';
                for (let i = 0; i < colCount; i++) {
                    const cell = cells[i] || '';
                    html += `<${tag}>${escapeHtml(cell)}</${tag}>`;
                }
                html += '</tr>';
            });
            html += '</table></div>';
            return html;
        }
        
        // 专门渲染 SIT 性能测试表 (固定2行表头)
        function renderSITPerformanceTable(parsedRows, colCount) {
            // 找到第一个数据行（包含"X并发"且有数值的行）
            let firstDataRowIdx = -1;
            for (let i = 0; i < parsedRows.length; i++) {
                const row = parsedRows[i];
                const hasConcurrency = row.some(cell => /\d+并发/.test(cell));
                const numericCount = row.filter(cell => /^\d+(\.\d+)?$/.test(cell.trim())).length;
                if (hasConcurrency && numericCount >= 3) {
                    firstDataRowIdx = i;
                    break;
                }
            }
            
            if (firstDataRowIdx === -1) {
                return renderPlainTable(parsedRows, colCount);
            }
            
            // 构建固定的2行表头
            let html = '<div class="table-wrapper"><table class="sit-table">';
            
            // 表头第一行
            html += '<thead>';
            html += '<tr class="header-row-1">';
            html += '<th rowspan="2" class="header-cell">并发数</th>';
            html += '<th rowspan="2" class="header-cell">版本</th>';
            html += '<th rowspan="2" class="header-cell">服务接口</th>';
            html += '<th colspan="7" class="header-cell colspan-header">性能指标</th>';
            html += '</tr>';
            
            // 表头第二行
            html += '<tr class="header-row-2">';
            html += '<th class="header-cell">请求总数</th>';
            html += '<th class="header-cell">平均响应<br>时间(ms)</th>';
            html += '<th class="header-cell">90%响应<br>时间(ms)</th>';
            html += '<th class="header-cell">95%响应<br>时间(ms)</th>';
            html += '<th class="header-cell">99%响应<br>时间(ms)</th>';
            html += '<th class="header-cell">吞吐率<br>TPS</th>';
            html += '<th class="header-cell">流量<br>KB/S</th>';
            html += '</tr>';
            html += '</thead>';
            
            // 渲染数据行
            html += '<tbody>';
            for (let i = firstDataRowIdx; i < parsedRows.length; i++) {
                const row = parsedRows[i];
                if (row.every(cell => !cell)) continue;
                if (row.some(cell => /性能指标|SIT测试|响应时间\(ms\)|吞吐率TPS/.test(cell))) continue;
                
                const concurrency = row[0] || '';
                const version = row[1] || '';
                const service = row[2] || '';
                
                const dataValues = [];
                for (let j = 3; j <= 9 && j < row.length; j++) {
                    dataValues.push(row[j] || '');
                }
                
                if (concurrency || dataValues.some(v => v)) {
                    html += '<tr>';
                    html += `<td class="col-concurrency">${escapeHtml(concurrency)}</td>`;
                    html += `<td class="col-version">${escapeHtml(version)}</td>`;
                    html += `<td class="col-service">${escapeHtml(service)}</td>`;
                    for (let j = 0; j < 7; j++) {
                        const val = dataValues[j] || '';
                        html += `<td class="col-numeric">${escapeHtml(val)}</td>`;
                    }
                    html += '</tr>';
                }
            }
            html += '</tbody>';
            html += '</table></div>';
            return html;
        }
        
        // 普通表格渲染
        function renderPlainTable(parsedRows, colCount) {
            let html = '<div class="table-wrapper"><table>';
            parsedRows.forEach((cells, idx) => {
                const isHeader = idx === 0;
                const tag = isHeader ? 'th' : 'td';
                html += '<tr>';
                for (let i = 0; i < colCount; i++) {
                    const cell = cells[i] || '';
                    html += `<${tag}>${escapeHtml(cell)}</${tag}>`;
                }
                html += '</tr>';
            });
            html += '</table></div>';
            return html;
        }
        
