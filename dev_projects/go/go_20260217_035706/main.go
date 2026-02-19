package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

// JiraIssue represents a Jira issue structure
type JiraIssue struct {
	ID          string `json:"id"`
	Key         string `json:"key"`
	Summary     string `json:"summary"`
	Description string `json:"description"`
}

// createJiraIssue sends a POST request to the Jira API to create an issue
func createJiraIssue(jiraURL, username, password, projectKey, summary, description string) (*JiraIssue, error) {
	// Prepare the JSON payload for the issue creation
	payload := map[string]string{
		"fields": json.RawMessage(fmt.Sprintf(`{"project":{"key":"%s"},"summary":"%s","description":"%s"}`, projectKey, summary, description)),
	}

	// Set up the HTTP request
	req, err := http.NewRequest("POST", jiraURL+"/rest/api/2/issue", ioutil.NopCloser(strings.NewReader(json.Marshal(payload))))
	if err != nil {
		return nil, fmt.Errorf("Error creating HTTP request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.SetBasicAuth(username, password)

	// Send the HTTP request
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("Error sending HTTP request: %v", err)
	}
	defer resp.Body.Close()

	// Check if the response was successful
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Failed to create issue. Status code: %d", resp.StatusCode)
	}

	// Parse the JSON response
	var issue JiraIssue
	err = json.Unmarshal(resp.Body, &issue)
	if err != nil {
		fmt.Println("Error parsing JSON response:", err)
		return nil, err
	}

	return &issue, nil
}

func main() {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := "your-username"
	password := "your-password"
	projectKey := "YOUR_PROJECT_KEY"
	summary := "Test Issue"
	description := "This is a test issue created by Go Agent."

	createdIssue, err := createJiraIssue(jiraURL, username, password, projectKey, summary, description)
	if err != nil {
		fmt.Println("Error creating Jira issue:", err)
		return
	}

	fmt.Printf("Created Issue: %+v\n", createdIssue)
}