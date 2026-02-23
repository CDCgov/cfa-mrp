use std::io::Write;

use csv::Writer;

pub struct CsvWriter {
    writer: Writer<Box<dyn Write>>,
}

impl CsvWriter {
    pub fn new(dest: Box<dyn Write>, headers: &[&str]) -> Self {
        let mut writer = Writer::from_writer(dest);
        writer.write_record(headers).expect("failed to write CSV headers");
        CsvWriter { writer }
    }

    pub fn write_row(&mut self, row: &[&str]) {
        self.writer.write_record(row).expect("failed to write CSV row");
    }

    pub fn flush(&mut self) {
        self.writer.flush().expect("failed to flush CSV writer");
    }
}

impl Drop for CsvWriter {
    fn drop(&mut self) {
        let _ = self.writer.flush();
    }
}
