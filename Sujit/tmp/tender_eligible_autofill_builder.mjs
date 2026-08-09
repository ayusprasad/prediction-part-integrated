import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const projectRoot = "C:/Users/kumar/Desktop/project2/Sujit";
const sourcePath = `${projectRoot}/data2/tender_exports/tender_plot_master.csv`;
const outputPath = `${projectRoot}/outputs/tender_eligible_plot_autofill.xlsx`;

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
      } else if (character === '"') quoted = false;
      else cell += character;
    } else if (character === '"') quoted = true;
    else if (character === ",") {
      row.push(cell); cell = "";
    } else if (character === "\n") {
      row.push(cell.replace(/\r$/, "")); rows.push(row); row = []; cell = "";
    } else cell += character;
  }
  if (cell || row.length) { row.push(cell.replace(/\r$/, "")); rows.push(row); }
  return rows;
}

function columnLetter(columnNumber) {
  let number = columnNumber;
  let result = "";
  while (number > 0) {
    const remainder = (number - 1) % 26;
    result = String.fromCharCode(65 + remainder) + result;
    number = Math.floor((number - 1) / 26);
  }
  return result;
}

function styleDataSheet(sheet, rows, tableName) {
  const columns = rows[0].length;
  const range = sheet.getRangeByIndexes(0, 0, rows.length, columns);
  range.format.wrapText = true;
  sheet.getRangeByIndexes(0, 0, 1, columns).format = {
    fill: "#0B2D52",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  sheet.tables.add(`A1:${columnLetter(columns)}${rows.length}`, true, tableName);
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;
  for (let column = 0; column < columns; column += 1) {
    const maxLength = Math.max(...rows.slice(0, 100).map((row) => String(row[column] ?? "").length));
    sheet.getRangeByIndexes(0, column, rows.length, 1).format.columnWidthPx = Math.max(95, Math.min(260, maxLength * 7 + 18));
  }
}

const allRows = parseCsv(await fs.readFile(sourcePath, "utf8"));
const header = allRows[0];
const indexByHeader = Object.fromEntries(header.map((name, index) => [name, index]));
const dropdownColumns = [
  "source_plot_id", "plot_code", "rr_no", "main_structure_name", "location",
  "city_survey_no", "city_survey_div", "plot_area_sqm", "plot_status", "plot_active", "is_vacant",
];
const dropdownRows = [
  dropdownColumns,
  ...allRows.slice(1)
    .filter((row) => String(row[indexByHeader.is_vacant] ?? "").trim().toLowerCase() === "true")
    .map((row) => dropdownColumns.map((column) => row[indexByHeader[column]] ?? "")),
];

const workbook = Workbook.create();
const eligibleSheet = workbook.worksheets.add("Eligible Vacant Plots");
eligibleSheet.getRange("A1:K1").values = [dropdownRows[0]];
eligibleSheet.getRangeByIndexes(1, 0, dropdownRows.length - 1, dropdownRows[0].length).values = dropdownRows.slice(1);
styleDataSheet(eligibleSheet, dropdownRows, "EligibleVacantPlots");

const autofillSheet = workbook.worksheets.add("Autofill Source");
autofillSheet.getRange("A1").writeValues(allRows);
styleDataSheet(autofillSheet, allRows, "TenderAutofillSource");

await fs.mkdir(`${projectRoot}/outputs`, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(outputPath);
