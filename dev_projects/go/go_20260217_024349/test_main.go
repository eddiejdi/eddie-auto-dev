package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

type JiraIssue struct {
	ID        string `json:"id"`
	Key       string `json:"key"`
	Project   struct {
		Key string `json:"key"`
	} `json:"project"`
	Summary  string `json:"summary"`
	Description string `json:"description"`
}

func createJiraIssue(jiraURL, username, password, projectKey, summary, description string) (*JiraIssue, error) {
	req, err := http.NewRequest("POST", jiraURL, bytes.NewBufferString(fmt.Sprintf(`{
		"fields": {
			"project": {
				"key": "%s"
			},
			"summary": "%s",
			"description": "%s"
		}
	}`, projectKey, summary, description)))
	if err != nil {
		return nil, fmt.Errorf("Error creating request: %v", err)
	}

	req.SetBasicAuth(username, password)

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("Error sending request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := ioutil.ReadAll(resp.Body)
		return nil, fmt.Errorf("Error creating Jira issue: %s", string(bodyBytes))
	}

	var issue JiraIssue
	err = json.Unmarshal(bodyBytes, &issue)
	if err != nil {
		return nil, fmt.Errorf("Error parsing JSON response: %v", err)
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