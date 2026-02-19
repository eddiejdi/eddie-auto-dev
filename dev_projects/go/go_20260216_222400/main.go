package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

// JiraIssue represents the structure of a Jira issue.
type JiraIssue struct {
	ID        string `json:"id"`
	Key       string `json:"key"`
	Project   struct {
		Key string `json:"key"`
	} `json:"project"`
	Summary    string `json:"summary"`
	Description string `json:"description"`
}

// createJiraIssue sends a POST request to the Jira API to create an issue.
func createJiraIssue(jiraURL, username, password, projectKey, summary, description string) (*JiraIssue, error) {
	issue := &JiraIssue{
		Key:       fmt.Sprintf("%s-%d", projectKey, 100),
		Summary:    summary,
		Description: description,
	}

	jsonBody, err := json.Marshal(issue)
	if err != nil {
		return nil, fmt.Errorf("Error marshaling JSON body: %v", err)
	}

	req, err := http.NewRequest(http.MethodPost, jiraURL, ioutil.NopCloser(bytes.NewBuffer(jsonBody)))
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
		return nil, fmt.Errorf("Unexpected status code: %d", resp.StatusCode)
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

	createdIssue, err := createJiraIssue(jiraURL, username, password, projectKey, summary, description)
	if err != nil {
		fmt.Println("Error creating Jira issue:", err)
		return
	}

	fmt.Printf("Created Issue: %+v\n", createdIssue)
}