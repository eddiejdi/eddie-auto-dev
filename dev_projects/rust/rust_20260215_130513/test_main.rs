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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_read_file_success() -> Result<(), Box<dyn Error>> {
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

        assert_eq!(issues.len(), 3); // Assuming the JSON file contains 3 issues
        Ok(())
    }

    #[test]
    fn test_read_file_error() -> Result<(), Box<dyn Error>> {
        let file_path = "nonexistent.json";
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

        assert_eq!(issues.len(), 0); // Assuming the JSON file does not contain any issues
        Ok(())
    }
}