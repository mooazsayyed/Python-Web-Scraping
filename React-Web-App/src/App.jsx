import { useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "property_csv";

const emptyForm = {
  title: "",
  price: "",
  location: "",
  bedrooms: "",
  bathrooms: "",
  area: ""
};

const headers = ["title", "price", "location", "bedrooms", "bathrooms", "area"];

function escapeCsv(value) {
  const safe = String(value ?? "");
  if (safe.includes('"') || safe.includes(",") || safe.includes("\n")) {
    return `"${safe.replace(/"/g, '""')}"`;
  }
  return safe;
}

function rowsToCsv(rows) {
  const lines = [headers.join(",")];
  rows.forEach((row) => {
    const line = headers.map((key) => escapeCsv(row[key])).join(",");
    lines.push(line);
  });
  return lines.join("\n");
}

function csvToRows(csvText) {
  if (!csvText) return [];
  const [headerLine, ...dataLines] = csvText.trim().split(/\r?\n/);
  if (!headerLine) return [];
  const parsedHeaders = headerLine.split(",").map((h) => h.trim());
  return dataLines.map((line) => {
    const values = [];
    let current = "";
    let inQuotes = false;
    for (let i = 0; i < line.length; i += 1) {
      const ch = line[i];
      if (ch === '"' && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else if (ch === '"') {
        inQuotes = !inQuotes;
      } else if (ch === "," && !inQuotes) {
        values.push(current);
        current = "";
      } else {
        current += ch;
      }
    }
    values.push(current);
    const row = {};
    parsedHeaders.forEach((key, idx) => {
      row[key] = values[idx] ?? "";
    });
    return row;
  });
}

function loadRows() {
  const stored = localStorage.getItem(STORAGE_KEY);
  return csvToRows(stored);
}

function saveRows(rows) {
  const csv = rowsToCsv(rows);
  localStorage.setItem(STORAGE_KEY, csv);
  return csv;
}

export default function App() {
  const [page, setPage] = useState("form");
  const [form, setForm] = useState(emptyForm);
  const [rows, setRows] = useState([]);
  const [csvText, setCsvText] = useState("");

  useEffect(() => {
    const initialRows = loadRows();
    setRows(initialRows);
    setCsvText(rowsToCsv(initialRows));
  }, []);

  const tableRows = useMemo(() => rows, [rows]);

  function handleChange(e) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  }

  function handleSubmit(e) {
    e.preventDefault();
    const newRows = [...rows, form];
    const csv = saveRows(newRows);
    setRows(newRows);
    setCsvText(csv);
    setForm(emptyForm);
    setPage("viewer");
  }

  function handleClear() {
    localStorage.removeItem(STORAGE_KEY);
    setRows([]);
    setCsvText(rowsToCsv([]));
  }

  function handleDownload() {
    const blob = new Blob([csvText], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "properties.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app">
      <header className="top">
        <h1>Property Form + Viewer</h1>
        <div className="tabs">
          <button
            className={page === "form" ? "active" : ""}
            onClick={() => setPage("form")}
            type="button"
          >
            Page 1: Form
          </button>
          <button
            className={page === "viewer" ? "active" : ""}
            onClick={() => setPage("viewer")}
            type="button"
          >
            Page 2: Viewer
          </button>
        </div>
      </header>

      {page === "form" && (
        <form className="card" onSubmit={handleSubmit}>
          <div className="grid">
            <label>
              Title
              <input
                name="title"
                value={form.title}
                onChange={handleChange}
                required
              />
            </label>
            <label>
              Price
              <input
                name="price"
                value={form.price}
                onChange={handleChange}
                required
              />
            </label>
            <label>
              Location
              <input
                name="location"
                value={form.location}
                onChange={handleChange}
                required
              />
            </label>
            <label>
              Bedrooms
              <input
                name="bedrooms"
                type="number"
                min="0"
                value={form.bedrooms}
                onChange={handleChange}
              />
            </label>
            <label>
              Bathrooms
              <input
                name="bathrooms"
                type="number"
                min="0"
                value={form.bathrooms}
                onChange={handleChange}
              />
            </label>
            <label>
              Area (sqft)
              <input
                name="area"
                value={form.area}
                onChange={handleChange}
              />
            </label>
          </div>
          <button className="primary" type="submit">
            Save to CSV
          </button>
        </form>
      )}

      {page === "viewer" && (
        <section className="card">
          <div className="viewer-actions">
            <button onClick={handleDownload} type="button">
              Download CSV
            </button>
            <button onClick={handleClear} type="button">
              Clear Data
            </button>
          </div>
          <p className="muted">
            Rows stored in CSV: {tableRows.length}
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  {headers.map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableRows.length === 0 && (
                  <tr>
                    <td colSpan={headers.length} className="empty">
                      No data yet.
                    </td>
                  </tr>
                )}
                {tableRows.map((row, idx) => (
                  <tr key={`${row.title}-${idx}`}>
                    {headers.map((h) => (
                      <td key={h}>{row[h]}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <details className="csv-preview">
            <summary>CSV preview</summary>
            <pre>{csvText}</pre>
          </details>
        </section>
      )}
    </div>
  );
}
