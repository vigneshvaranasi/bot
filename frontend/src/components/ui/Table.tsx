import React from "react";
import { Button } from "../ui/Button"; 

type TableColumn<T> = {
  header: string;
  accessor?: keyof T;
  render?: (row: T) => React.ReactNode;
  className?: string;
  headerClassName?: string;
};

interface TableProps<T> {
  columns: TableColumn<T>[];
  data: T[];
  tableClassName?: string;
  headerRowClassName?: string;
  rowClassName?: string;
  keyExtractor?: (row: T, index: number) => string | number;
}

export function ConfigurableTable<T>({
  columns,
  data,            

  tableClassName = "min-w-full border-2 border-gray-300 rounded-lg overflow-hidden border-separate", 
  headerRowClassName = "bg-white",
  rowClassName = "bg-white border-t border-gray-400",
  keyExtractor,
}: TableProps<T>) {
  return (
    <table className={tableClassName} style={{ borderSpacing: 0 }}>
      <thead>
        <tr className={headerRowClassName}>
          {columns.map((col, colIndex) => (
            <th
              key={colIndex}
              className={`px-4 py-3 text-left ${col.headerClassName || "font-semibold text-gray-800"}`}
            >
              {col.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row, rowIndex) => (
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
                  ? col.render(row)
                  : col.accessor
                  ? (row[col.accessor] as React.ReactNode)
                  : null}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
