use std::error::Error;
use std::fs::File;
use std::io::{self, BufRead};
use serde_json::Value;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

fn main() -> Result<(), Box<dyn Error>> {
    let file_path = "issues.json";
    let mut issues: Vec<JiraIssue> = vec![];

    if let Ok(file) = File::open(file_path) {
        for line in io::BufRead::lines(file)? {
            let issue_str = line?;
            if let Ok(issue_json) = serde_json::from_str(&issue_str) {
                let issue: JiraIssue = serde_json::from_value(issue_json)?;
                issues.push(issue);
            }
        }
    } else {
        eprintln!("Error opening file: {}", file_path);
        return Err(Box::new(io::Error::new(io::ErrorKind::NotFound, "File not found")));
    }

    for issue in &issues {
        println!("Key: {}, Summary: {}, Status: {}", issue.key, issue.summary, issue.status);
    }

    Ok(())
}