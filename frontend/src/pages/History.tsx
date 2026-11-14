import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDownUp, Plus, Trash2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useAudits } from "../api/hooks";
import { request } from "../api/client";
import type { AuditListItem } from "../api/types";
import { fmtDate, fmtPct } from "../lib/format";
export default function History() {
  const [offset, setOffset] = useState(0),
    [sorting, setSorting] = useState<SortingState>([]),
    [error, setError] = useState("");
  const audits = useAudits({ limit: 50, offset }),
    navigate = useNavigate(),
    client = useQueryClient();
  const cols = useMemo<ColumnDef<AuditListItem>[]>(
    () => [
      {
        accessorKey: "created_at",
        header: "Created",
        cell: (c) => fmtDate(c.getValue<string>()),
      },
      {
        accessorKey: "template",
        header: "Strategy",
        cell: (c) => c.getValue<string>().replaceAll("_", " "),
      },
      { accessorKey: "generator", header: "Generator" },
      {
        accessorKey: "n_histories",
        header: "Histories",
        cell: (c) => c.getValue<number>().toLocaleString(),
      },
      {
        accessorKey: "verdict",
        header: "Verdict",
        cell: (c) => (
          <span className={`verdict-chip ${c.getValue() || ""}`}>
            {c.getValue<string>() || "—"}
          </span>
        ),
      },
      { accessorKey: "status", header: "Status" },
      {
        id: "survival",
        header: "Survival",
        accessorFn: (r) => r.metrics?.survival_rate,
        cell: (c) =>
          c.getValue() == null ? "—" : fmtPct(c.getValue<number>()),
      },
      {
        id: "delete",
        header: "",
        cell: (c) => (
          <button
            className="icon-button"
            aria-label={`Delete audit ${c.row.original.id}`}
            onClick={async (e) => {
              e.stopPropagation();
              try {
                await request(`/audits/${c.row.original.id}`, {
                  method: "DELETE",
                });
                await client.invalidateQueries({ queryKey: ["audits"] });
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            <Trash2 size={15} />
          </button>
        ),
      },
    ],
    [client],
  );
  const table = useReactTable({
    data: audits.data?.items || [],
    columns: cols,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">YOUR RESEARCH LOG</div>
          <h1>Every question. Every result.</h1>
          <p>Revisit the evidence behind your strategies.</p>
        </div>
        <Link className="button primary" to="/audit/new">
          <Plus size={16} /> New audit
        </Link>
      </div>
      <div className="panel history-panel">
        {audits.isPending ? (
          <p>Loading audits…</p>
        ) : audits.error ? (
          <div role="alert">
            <p>{audits.error.message}</p>
            <button onClick={() => audits.refetch()}>Try again</button>
          </div>
        ) : !audits.data?.items.length ? (
          <div className="empty-state">
            <h2>Your first audit starts here.</h2>
            <p>Build a strategy to see its results in your research log.</p>
            <Link className="button outline" to="/audit/new">
              Build a strategy
            </Link>
          </div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                {table.getHeaderGroups().map((g) => (
                  <tr key={g.id}>
                    {g.headers.map((h) => (
                      <th key={h.id}>
                        <button onClick={h.column.getToggleSortingHandler()}>
                          {flexRender(
                            h.column.columnDef.header,
                            h.getContext(),
                          )}
                          {h.column.getCanSort() && <ArrowDownUp size={11} />}
                        </button>
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    tabIndex={0}
                    onClick={() =>
                      navigate(
                        `/audit/${row.original.id}${["queued", "running"].includes(row.original.status) ? "/run" : ""}`,
                      )
                    }
                    onKeyDown={(e) =>
                      e.key === "Enter" && navigate(`/audit/${row.original.id}`)
                    }
                  >
                    {row.getVisibleCells().map((c) => (
                      <td key={c.id}>
                        {flexRender(c.column.columnDef.cell, c.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {error && <p role="alert">{error}</p>}
        <div className="pagination">
          <span>{audits.data?.total || 0} audits</span>
          <button
            disabled={!offset}
            onClick={() => setOffset(Math.max(0, offset - 50))}
          >
            Previous
          </button>
          <button
            disabled={offset + 50 >= (audits.data?.total || 0)}
            onClick={() => setOffset(offset + 50)}
          >
            Next
          </button>
        </div>
      </div>
    </>
  );
}
