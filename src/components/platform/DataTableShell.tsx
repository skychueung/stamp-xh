import type { ReactNode } from 'react';

interface Column<T> {
  header: string;
  render: (row: T) => ReactNode;
}

interface DataTableShellProps<T = any> {
  children?: ReactNode;
  className?: string;
  data?: T[];
  columns?: Column<T>[];
}

export function DataTableShell<T>({ children, className = '', data, columns }: DataTableShellProps<T>) {
  if (data && columns) {
    return (
      <div className={`overflow-x-auto rounded-lg border border-xh-border ${className}`}>
        <table className="w-full min-w-[800px] text-sm text-left">
          <thead className="bg-slate-50 text-slate-600 text-xs uppercase tracking-wider">
            <tr>
              {columns.map((col, i) => (
                <th key={i} className="px-4 py-3 font-semibold border-b border-xh-border">{col.header}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-xh-border">
            {data.map((row, rowIndex) => (
              <tr key={rowIndex} className="hover:bg-slate-50 transition-colors">
                {columns.map((col, colIndex) => (
                  <td key={colIndex} className="px-4 py-3">
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className={`overflow-x-auto rounded-lg border border-xh-border ${className}`}>
      <table className="w-full min-w-[800px] text-sm text-left">
        {children}
      </table>
    </div>
  );
}
