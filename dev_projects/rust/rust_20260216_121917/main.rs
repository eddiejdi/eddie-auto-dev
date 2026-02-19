use std::fs;
use std::io::{self, Write};
use serde_json;

// Define a struct to represent an issue in Jira
#[derive(Deserialize)]
struct Issue {
    key: String,
    summary: String,
    status: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Read the JSON data from the file
    let file_path = "issues.json";
    if !fs::path_exists(file_path) {
        return Err("File not found".into());
    }

    let mut file = fs::File::open(file_path)?;
    let mut content = String::new();
    io::read_to_string(&mut file, &mut content)?;

    // Parse the JSON data into a vector of Issue structs
    let issues: Vec<Issue> = serde_json::from_str(&content)?;

    // Print the issue summary for each issue
    for issue in issues {
        println!("Key: {}, Summary: {}", issue.key, issue.summary);
    }

    Ok(())
}