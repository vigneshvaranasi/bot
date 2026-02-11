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
  tableClassName = "min-w-full border-1 border-gray-300 rounded-lg overflow-hidden border-separate", 
  headerRowClassName = "bg-white",
  rowClassName = "bg-white border-t border-gray-400",
  keyExtractor,
  searchButtonClassName = "ml-2 px-2 py-1 text-xs  text-white rounded focus:outline-none",
  searchInputClassName = "px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500",
  searchContainerClassName = "mb-4 p-3 bg-gray-50 border border-gray-200 rounded-lg",
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
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-700">
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
              className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 focus:outline-none"
            >
              Search
            </button>
            <button
              onClick={() => handleSearchReset(activeSearchColumn)}
              className="px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600 focus:outline-none"
            >
              Reset
            </button>
            <button
              onClick={() => setActiveSearchColumn(null)}
              className="px-2 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600 focus:outline-none"
            >
              ✕
            </button>
          </div>
          {Object.keys(appliedFilters).length > 0 && (
            <div className="mt-2 text-xs text-gray-600">
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
                className={`px-4 py-3 text-left ${col.headerClassName || "font-semibold text-gray-800"}`}
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
                      <img src={searchIcon} alt="Search" />
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
                  className={`px-4 py-3 ${col.className || "text-gray-700"}`}
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
        <div className="text-center py-8 text-gray-500">
          No results found. Try adjusting your search.
        </div>
      )}
    </div>
  );
}
