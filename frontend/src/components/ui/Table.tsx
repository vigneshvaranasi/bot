import React, { useState, useMemo } from "react";
import searchIcon from "../../assets/SearchIcon.svg";
type TableColumn<T> = {
  header: string;
  accessor?: keyof T;
  render?: (row: T, index: number) => React.ReactNode;
  className?: string;
  headerClassName?: string;
  searchable?: boolean;
};

interface TableProps<T> {
  columns: TableColumn<T>[];
  data: T[];
  tableClassName?: string;
  headerRowClassName?: string;
  rowClassName?: string;
  keyExtractor?: (row: T, index: number) => string | number;
  searchButtonClassName?: string;
  searchInputClassName?: string;
  searchContainerClassName?: string;
}

export function ConfigurableTable<T>({
  columns,
  data,            
  tableClassName = "min-w-full border-1 border-border-strong rounded-lg overflow-hidden border-separate",
  headerRowClassName = "bg-surface-primary",
  rowClassName = "bg-surface-primary border-t border-border-default",
  keyExtractor,
  searchButtonClassName = "ml-2 px-2 py-1 text-xs text-text-inverse rounded focus:outline-none",
  searchInputClassName = "px-2 py-1 text-sm border border-border-default bg-surface-primary text-text-primary rounded focus:outline-none focus:ring-1 focus:ring-accent-blue",
  searchContainerClassName = "mb-4 p-3 bg-surface-tertiary border border-border-default rounded-lg",
}: TableProps<T>) {
  const [activeSearchColumn, setActiveSearchColumn] = useState<number | null>(null);
  const [searchQueries, setSearchQueries] = useState<{[key: number]: string}>({});
  const [appliedFilters, setAppliedFilters] = useState<{[key: number]: string}>({});

  const hasSearchableColumns = columns.some(col => col.searchable !== false);

  const fuzzyMatch = (text: string, query: string): boolean => {
    if (!query) return true;
    
    const textLower = text.toLowerCase();
    const queryLower = query.toLowerCase();
    let queryIndex = 0;
    for (let i = 0; i < textLower.length && queryIndex < queryLower.length; i++) {
      if (textLower[i] === queryLower[queryIndex]) {
        queryIndex++;
      }
    }
    return queryIndex === queryLower.length;
  };
const getCellValue = (row: T, col: TableColumn<T>, rowIndex: number): string => {
    if (col.render) {
      const rendered = col.render(row, rowIndex);
      return typeof rendered === "string" ? rendered : String(rendered);
    } else if (col.accessor) {
      const value = row[col.accessor];
      return value != null ? String(value) : "";
    }
    return "";
  };

  const filteredData = useMemo(() => {
    if (Object.keys(appliedFilters).length === 0) return data;

    return data.filter((row, rowIndex) => {
      return Object.entries(appliedFilters).every(([colIndex, query]) => {
        const column = columns[parseInt(colIndex)];
        if (!column || column.searchable === false) return true;

        const cellValue = getCellValue(row, column, rowIndex);
        return fuzzyMatch(cellValue, query);
      });
    });
  }, [data, appliedFilters, columns]);

  const handleSearchClick = (colIndex: number) => {
    if (activeSearchColumn === colIndex) {
      setActiveSearchColumn(null);
    } else {
      setActiveSearchColumn(colIndex);
      if (!(colIndex in searchQueries)) {
        setSearchQueries(prev => ({ ...prev, [colIndex]: appliedFilters[colIndex] || "" }));
      }
    }
  };

  const handleSearchSubmit = (colIndex: number) => {
    const query = searchQueries[colIndex] || "";
    if (query.trim()) {
      setAppliedFilters(prev => ({ ...prev, [colIndex]: query.trim() }));
    } else {
      setAppliedFilters(prev => {
        const newFilters = { ...prev };
        delete newFilters[colIndex];
        return newFilters;
      });
    }
    setActiveSearchColumn(null);
  };

  const handleSearchReset = (colIndex: number) => {
    setSearchQueries(prev => ({ ...prev, [colIndex]: "" }));
    setAppliedFilters(prev => {
      const newFilters = { ...prev };
      delete newFilters[colIndex];
      return newFilters;
    });
    setActiveSearchColumn(null);
  };

  const handleKeyPress = (e: React.KeyboardEvent, colIndex: number) => {
    if (e.key === 'Enter') {
      handleSearchSubmit(colIndex);
    } else if (e.key === 'Escape') {
      setActiveSearchColumn(null);
    }
  };

  return (
    <div>
      {/* Search Container */}
      {hasSearchableColumns && activeSearchColumn !== null && (
        <div className={searchContainerClassName}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-text-secondary">
              Search in "{columns[activeSearchColumn].header}":
            </span>
            <input
              type="text"
              value={searchQueries[activeSearchColumn] || ""}
              onChange={(e) => setSearchQueries(prev => ({
                ...prev,
                [activeSearchColumn]: e.target.value
              }))}
              onKeyDown={(e) => handleKeyPress(e, activeSearchColumn)}
              className={searchInputClassName}
              placeholder={`Search ${columns[activeSearchColumn].header.toLowerCase()}...`}
              autoFocus
            />
            <button
              onClick={() => handleSearchSubmit(activeSearchColumn)}
              className="px-3 py-1 text-sm bg-accent-blue text-white rounded hover:bg-accent-blue-hover focus:outline-none"
            >
              Search
            </button>
            <button
              onClick={() => handleSearchReset(activeSearchColumn)}
              className="px-3 py-1 text-sm bg-btn-secondary text-white rounded hover:bg-btn-secondary-hover focus:outline-none"
            >
              Reset
            </button>
            <button
              onClick={() => setActiveSearchColumn(null)}
              className="px-2 py-1 text-sm bg-btn-secondary text-white rounded hover:bg-btn-secondary-hover focus:outline-none"
            >
              ✕
            </button>
          </div>
          {Object.keys(appliedFilters).length > 0 && (
            <div className="mt-2 text-xs text-text-secondary">
              Active filters: {Object.entries(appliedFilters).map(([colIndex, query]) => 
                `${columns[parseInt(colIndex)].header}: "${query}"`
              ).join(', ')}
            </div>
          )}
        </div>
      )}

      <table className={tableClassName} style={{ borderSpacing: 0 }}>
        <thead>
          <tr className={headerRowClassName}>
            {columns.map((col, colIndex) => (
              <th
                key={colIndex}
                className={`px-4 py-3 text-left ${col.headerClassName || "font-semibold text-text-primary"}`}
              >
                <div className="flex items-center justify-between">
                  <span>{col.header}</span>
                  {col.searchable !== false && (
                    <button
                      onClick={() => handleSearchClick(colIndex)}
                      className={`${searchButtonClassName} ${
                        appliedFilters[colIndex] ? '' : ''
                      } ${activeSearchColumn === colIndex ? '' : ''}`}
                    >
                      <img src={searchIcon} alt="Search" className="icon-adaptive" />
                    </button>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filteredData.map((row, rowIndex) => (
            <tr
              key={keyExtractor ? keyExtractor(row, rowIndex) : rowIndex}
              className={rowClassName}
            >
              {columns.map((col, colIndex) => (
                <td
                  key={colIndex}
                  className={`px-4 py-3 align-middle ${col.className || "text-text-secondary"}`}
                >
                  {col.render
                    ? col.render(row, rowIndex)
                    : col.accessor
                    ? (row[col.accessor] as React.ReactNode)
                    : null}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      
      {filteredData.length === 0 && data.length > 0 && (
        <div className="text-center py-8 text-text-secondary">
          No results found. Try adjusting your search.
        </div>
      )}
    </div>
  );
}
