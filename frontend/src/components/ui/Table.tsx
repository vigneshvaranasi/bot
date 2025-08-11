import React from "react";
import { Button } from "./Button"; // your existing configurable Button

type TableColumn<T> = {
  header: string;
  accessor?: keyof T; // key in data object
  render?: (row: T) => React.ReactNode; // custom render function
  className?: string;
};

interface TableProps<T> {
  columns: TableColumn<T>[];
  data: T[];
  tableClassName?: string;
  headerClassName?: string;
  rowClassName?: string;
  keyExtractor?: (row: T, index: number) => string | number;
}

export function ConfigurableTable<T>({ 
  columns,
  data,
  tableClassName = "min-w-full border border-gray-300",
  headerClassName = "bg-gray-100 font-semibold text-left px-4 py-2",
  rowClassName = "border-t border-gray-200",
  keyExtractor,
}: TableProps<T>) {
  return (
    <table className={tableClassName}>
      <thead>
        <tr>
          {columns.map((col, colIndex) => (
            <th key={colIndex} className={headerClassName}>
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
              <td key={colIndex} className={`px-4 py-2 ${col.className || ""}`}>
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

// =========================
// Example Usage
// =========================

type UserRow = {
  email: string;
  role: string;
  permissions: string;
  lastUpdated: string;
};

const userData: UserRow[] = [
  {
    email: "emp1@gmail.com",
    role: "L1 Support",
    permissions: "Access Chat, Rating",
    lastUpdated: "27 July 2025",
  },
  {
    email: "emp2@gmail.com",
    role: "L2 Support",
    permissions: "Access Chat",
    lastUpdated: "28 July 2025",
  },
];

export default function UserTableDemo() {
  return (
    <ConfigurableTable<UserRow>
      columns={[
        { header: "Email", accessor: "email" },
        { header: "Role", accessor: "role" },
        { header: "Permissions", accessor: "permissions" },
        { header: "Last Updated", accessor: "lastUpdated" },
        {
          header: "Actions",
          render: (row) => (
            <div className="flex gap-2">
              <Button variant="primary" onClick={() => alert(`Editing ${row.email}`)}>
                Edit
              </Button>
              <Button
                variant="secondary"
                onClick={() => alert(`Deleting ${row.email}`)}
              >
                Delete
              </Button>
            </div>
          ),
        },
      ]}
      data={userData}
    />
  );
}
