const path = require("path");

class DocumentParser {
  /**
   * Parses buffer into plain text based on file name or mime type
   * @param {Buffer} buffer 
   * @param {string} fileName 
   * @param {string} mimeType 
   * @returns {Promise<string>}
   */
  async parseBuffer(buffer, fileName = "", mimeType = "") {
    const ext = path.extname(fileName).toLowerCase();

    // Plain text formats
    if (
      ext === ".txt" ||
      ext === ".md" ||
      ext === ".markdown" ||
      ext === ".json" ||
      ext === ".csv" ||
      mimeType.startsWith("text/")
    ) {
      return buffer.toString("utf8");
    }

    // PDF documents
    if (ext === ".pdf" || mimeType === "application/pdf") {
      try {
        const { PDFParse } = require("pdf-parse");
        const parser = new PDFParse({ data: buffer });
        const res = await parser.getText();
        return res.text || "";
      } catch (err) {
        console.warn(`[DocumentParser] PDF parsing error for ${fileName}:`, err.message);
        return buffer.toString("utf8").replace(/[^\x20-\x7E\n\r\t]/g, " ");
      }
    }

    // Word documents (.docx)
    if (
      ext === ".docx" ||
      mimeType === "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ) {
      try {
        const mammoth = require("mammoth");
        const result = await mammoth.extractRawText({ buffer });
        return result.value || "";
      } catch (err) {
        console.warn(`[DocumentParser] DOCX parsing error for ${fileName}:`, err.message);
        return buffer.toString("utf8").replace(/[^\x20-\x7E\n\r\t]/g, " ");
      }
    }

    // Default fallback to UTF-8
    return buffer.toString("utf8").replace(/[^\x20-\x7E\n\r\t]/g, " ");
  }
}

module.exports = new DocumentParser();
