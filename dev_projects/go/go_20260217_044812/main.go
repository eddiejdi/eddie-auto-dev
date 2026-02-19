package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

// JiraIssue represents a Jira issue
type JiraIssue struct {
	ID        string `json:"id"`
	Key       string `json:"key"`
	Type      string `json:"type"`
	Summary   string `json:"summary"`
	Description string `json:"description"`
}

// CreateJiraIssue sends a POST request to create a new Jira issue
func createJiraIssue(jiraURL, username, password, projectKey, summary, description string) (*JiraIssue, error) {
	issue := &JiraIssue{
		Key:       fmt.Sprintf("%s-%s", projectKey, summary),
		Summary:   summary,
		Description: description,
	}

	jsonBody, err := json.Marshal(issue)
	if err != nil {
		return nil, fmt.Errorf("Error marshaling JSON issue: %v", err)
	}

	req, err := http.NewRequest("POST", jiraURL+"/rest/api/2/issue", ioutil.NopCloser(bytes.NewBuffer(jsonBody)))
	if err != nil {
		return nil, fmt.Errorf("Error creating request: %v", err)
	}
	req.SetBasicAuth(username, password)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("Error sending request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return nil, fmt.Errorf("Failed to create issue. Status code: %d", resp.StatusCode)
	}

	var createdIssue JiraIssue
	err = json.NewDecoder(resp.Body).Decode(&createdIssue)
	if err != nil {
		return nil, fmt.Errorf("Error parsing JSON response: %v", err)
	}

	return &createdIssue, nil
}

func main() {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := "your-username"
	password := "your-password"
	projectKey := "YOUR_PROJECT_KEY"
	summary := "Test Issue"
	description := "This is a test issue created by Go Agent."

	if err := createJiraIssue(jiraURL, username, password, projectKey, summary, description); err != nil {
		fmt.Println("Error creating Jira issue:", err)
		return
	}

	fmt.Printf("Created Issue: %+v\n", createdIssue)
}