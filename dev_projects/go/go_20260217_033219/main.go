package main

import (
	"encoding/csv"
	"fmt"
	"io/ioutil"
	"net/http"
)

// JiraIssue represents a Jira issue
type JiraIssue struct {
	ID        string `json:"id"`
	Key       string `json:"key"`
	Summary   string `json:"summary"`
	Description string `json:"description"`
}

// ReadCSV reads CSV data from a file and returns a slice of JiraIssues
func ReadCSV(filePath string) ([]JiraIssue, error) {
	var issues []JiraIssue

	file, err := ioutil.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("Error reading CSV file: %v", err)
	}

	reader := csv.NewReader(strings.NewReader(string(file)))
	for _, err = reader.Read(); err == nil; {
		id := reader.Text(0)
		key := reader.Text(1)
		summary := reader.Text(2)
		description := reader.Text(3)

		issues = append(issues, JiraIssue{
			ID:        id,
			Key:       key,
			Summary:   summary,
			Description: description,
		})
	}

	return issues, nil
}

// DeleteJiraIssues deletes Jira issues from the specified project key
func DeleteJiraIssues(jiraURL string, username, password, projectKey string) error {
	client := &http.Client{}

	for _, issue := range issues {
		url := fmt.Sprintf("%s/rest/api/2/issue/%s", jiraURL, issue.Key)
		req, err := http.NewRequest("DELETE", url, nil)
		if err != nil {
			return fmt.Errorf("Error creating request: %v", err)
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Authorization", fmt.Sprintf("Basic %s", base64.StdEncoding.EncodeToString([]byte(fmt.Sprintf("%s:%s", username, password)))))

		resp, err := client.Do(req)
		if err != nil {
			return fmt.Errorf("Error sending request: %v", err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			return fmt.Errorf("Failed to delete issue %s: %s", issue.Key, resp.Status)
		}
	}

	fmt.Println("All issues deleted successfully.")
	return nil
}

func main() {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2"
	username := "your-username"
	password := "your-password"
	projectKey := "YOUR_PROJECT_KEY"

	// Read CSV data from a file
	filePath := "path/to/your/issues.csv"
	issues, err := ReadCSV(filePath)
	if err != nil {
		fmt.Println("Error reading CSV file:", err)
		return
	}

	// Delete Jira issues from the specified project key
	err = DeleteJiraIssues(jiraURL, username, password, projectKey)
	if err != nil {
		fmt.Println("Error deleting Jira issues:", err)
		return
	}
}