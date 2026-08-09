import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const projectRoot = "C:/Users/kumar/Desktop/project2/Sujit";
const manifestPath = path.join(projectRoot, "config/tender_export_manifest.json");
const workflowConfigPath = path.join(projectRoot, "config/tender_workflow.json");
const outputPath = path.join(projectRoot, "outputs/tender_workflow_source_pack.xlsx");

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoted) {
      if (character === '"' && text[index + 1] === '"') {
        cell += '"';
        index += 1;
      } else if (character === '"') {
        quoted = false;
      } else {
        cell += character;
      }
    } else if (character === '"') {
      quoted = true;
    } else if (character === ",") {
      row.push(cell);
      cell = "";
    } else if (character === "\n") {
      row.push(cell.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += character;
    }
  }
  if (cell || row.length) {
    row.push(cell.replace(/\r$/, ""));
    rows.push(row);
  }
  return rows;
}

function sheetNameFor(name) {
  return {
    tender_plot_master: "Plot Master",
    tender_plot_area_history: "Area History",
    tender_tenancy_reference: "Tenancy Reference",
    tender_application_reference: "Application Reference",
    tender_rate_reference: "Rate Reference",
    tender_source_coverage: "Coverage",
  }[name] || name.slice(0, 31);
}

function columnLetter(columnNumber) {
  let number = columnNumber;
  let letters = "";
  while (number > 0) {
    const remainder = (number - 1) % 26;
    letters = String.fromCharCode(65 + remainder) + letters;
    number = Math.floor((number - 1) / 26);
  }
  return letters;
}

function fitColumns(sheet, rows) {
  const columnCount = rows[0]?.length || 1;
  for (let column = 0; column < columnCount; column += 1) {
    const sampleLengths = rows.slice(0, 80).map((row) => String(row[column] ?? "").length);
    const width = Math.max(90, Math.min(260, Math.max(...sampleLengths, 0) * 7 + 20));
    sheet.getRangeByIndexes(0, column, Math.max(rows.length, 1), 1).format.columnWidthPx = width;
  }
}

async function main() {
  const manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"));
  const workflowConfig = JSON.parse(await fs.readFile(workflowConfigPath, "utf8"));
  const workbook = Workbook.create();
  const navy = "#0B2D52";
  const gold = "#D97706";
  const lightBlue = "#EEF5FB";

  const overview = workbook.worksheets.add("Overview");
  overview.showGridLines = false;
  overview.mergeCells("A1:D1");
  overview.getRange("A1").values = [["Tender Publication Workflow - Source Data Pack"]];
  overview.getRange("A1:D1").format = { fill: navy, font: { bold: true, color: "#FFFFFF", size: 16 }, horizontalAlignment: "center" };
  overview.getRange("A3:B6").values = [
    ["Purpose", "The exported public-database data used for the tender workflow plot dropdown and safe autofill."],
    ["Primary autofill source", "Plot Master sheet / tender_plot_master.csv"],
    ["Selection rule", `${workflowConfig.plot_source.eligibility_field} in (${workflowConfig.plot_source.eligible_values.join(", ")})`],
    ["Autofill mapping", Object.entries(workflowConfig.plot_source.prefill_fields).map(([target, source]) => `${target} <- ${source}`).join("; ")],
  ];
  overview.getRange("A3:A6").format = { fill: lightBlue, font: { bold: true, color: navy }, wrapText: true };
  overview.getRange("B3:B6").format = { wrapText: true };
  overview.getRange("A8:D8").values = [["Sheet", "CSV file", "Purpose", "Workflow use"]];
  overview.getRange("A8:D8").format = { fill: navy, font: { bold: true, color: "#FFFFFF" } };
  const overviewRows = manifest.exports.map((item) => [
    sheetNameFor(item.name),
    item.filename,
    item.purpose,
    item.name === workflowConfig.plot_source.source_key ? "Used for dropdown and area autofill" : "Reference/evidence export",
  ]);
  overview.getRangeByIndexes(8, 0, overviewRows.length, 4).values = overviewRows;
  overview.getRangeByIndexes(8, 0, overviewRows.length, 4).format = { wrapText: true, borders: { preset: "all", style: "thin", color: "#D9E2EC" } };
  overview.getRange("A1:D20").format.columnWidth = 24;
  overview.getRange("B3").format.columnWidth = 72;
  overview.getRange("C9").format.columnWidth = 68;
  overview.getRange("D9").format.columnWidth = 38;
  overview.freezePanes.freezeRows(1);

  for (const exportItem of manifest.exports) {
    const sourcePath = path.join(projectRoot, manifest.output_directory, exportItem.filename);
    const csvRows = parseCsv(await fs.readFile(sourcePath, "utf8"));
    const sheet = workbook.worksheets.add(sheetNameFor(exportItem.name));
    sheet.showGridLines = false;
    sheet.getRangeByIndexes(0, 0, csvRows.length, csvRows[0].length).values = csvRows;
    const used = sheet.getRangeByIndexes(0, 0, csvRows.length, csvRows[0].length);
    used.format.wrapText = true;
    used.format.borders = { preset: "all", style: "thin", color: "#E2E8F0" };
    sheet.getRangeByIndexes(0, 0, 1, csvRows[0].length).format = { fill: navy, font: { bold: true, color: "#FFFFFF" }, wrapText: true };
    sheet.freezePanes.freezeRows(1);
    if (csvRows[0].length > 0 && csvRows.length > 1) {
      sheet.tables.add(`A1:${columnLetter(csvRows[0].length)}${csvRows.length}`, true, `Table_${exportItem.name}`);
    }
    fitColumns(sheet, csvRows);
  }

  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outputPath);
  console.log(outputPath);
}

await main();
