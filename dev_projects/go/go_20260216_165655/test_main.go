package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

// JiraIssue represents the structure of a Jira issue
type JiraIssue struct {
	ID        string `json:"id"`
	Key       string `json:"key"`
	Project  struct {
		Key string `json:"key"`
	} `json:"project"`
	Summary string `json:"summary"`
	Description string `json:"description"`
}

// createJiraIssue sends a POST request to the Jira API to create an issue
func createJiraIssue(jiraURL, username, password, projectKey, summary, description string) (*JiraIssue, error) {
	issue := JiraIssue{
		Key:       fmt.Sprintf("%s-%d", projectKey, 1),
		Summary: summary,
		Description: description,
	}

	jsonData, err := json.Marshal(issue)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequest("POST", jiraURL, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, err
	}
	req.SetBasicAuth(username, password)

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		bodyBytes, _ := ioutil.ReadAll(resp.Body)
		return nil, fmt.Errorf("Error creating Jira issue: %s", bodyBytes)
	}

	var createdIssue JiraIssue
	err = json.NewDecoder(resp.Body).Decode(&createdIssue)
	if err != nil {
		return nil, err
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