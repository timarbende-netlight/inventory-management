// CSV export helpers, reusable across views.

// Wraps a number so toCsv writes it verbatim (e.g. fixed decimals) and skips
// the formula-injection prefix below, which would otherwise corrupt negatives.
export function csvNumber(value, decimals = 2) {
  return { csvNumeric: Number(value).toFixed(decimals) }
}

function escapeField(value) {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object' && 'csvNumeric' in value) return value.csvNumeric
  if (typeof value === 'number') return String(value)

  let text = String(value)

  // Formula injection: spreadsheets execute cells starting with = + - @ as
  // formulas. A leading single quote forces the cell to be read as plain text.
  if (/^[=+\-@]/.test(text)) text = `'${text}`

  // RFC 4180: fields containing comma, quote or newline must be quoted, and
  // embedded quotes are escaped by doubling them.
  if (/[",\r\n]/.test(text)) text = `"${text.replace(/"/g, '""')}"`
  return text
}

export function toCsv(headers, rows) {
  return [headers, ...rows]
    .map(row => row.map(escapeField).join(','))
    .join('\r\n')
}

export function downloadCsv(filename, csvString) {
  // The UTF-8 BOM makes Excel detect the encoding; without it, Japanese text
  // is decoded as the system ANSI codepage and shows up garbled.
  const blob = new Blob(['﻿' + csvString], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
