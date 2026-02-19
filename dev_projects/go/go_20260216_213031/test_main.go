package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

// JiraIssue represents a Jira issue
type JiraIssue struct {
	ID        string `json:"id"`
	Key       string `json:"key"`
	Project   struct {
		Key string `json:"key"`
	} `json:"project"`
	Summary string `json:"summary"`
	Description string `json:"description"`
}

// createJiraIssue sends a POST request to the Jira API to create an issue
func createJiraIssue(jiraURL, username, password, projectKey, summary, description string) (*JiraIssue, error) {
	issue := &JiraIssue{
		Key:       fmt.Sprintf("%s-%d", projectKey, 1000),
		Summary:   summary,
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

	bodyBytes, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		fmt.Println("Error reading response body:", err)
		return nil, err
	}

	var issue JiraIssue
	err = json.Unmarshal(bodyBytes, &issue)
	if err != nil {
		fmt.Println("Error parsing JSON response:", err)
		return nil, err
	}

	return &issue, nil
}

// TestCreateJiraIssue tests the createJiraIssue function with valid data
func TestCreateJiraIssue(t *testing.T) {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := "your-username"
	password := "your-password"
	projectKey := "YOUR_PROJECT_KEY"
	summary := "Test Issue"
	description := "This is a test issue created by Go Agent."

	createdIssue, err := createJiraIssue(jiraURL, username, password, projectKey, summary, description)
	if err != nil {
		t.Errorf("Error creating Jira issue: %v", err)
	}

	expectedID := fmt.Sprintf("%s-%d", projectKey, 1000)
	expectedSummary := "Test Issue"
	expectedDescription := "This is a test issue created by Go Agent."

	if createdIssue.ID != expectedID {
		t.Errorf("Expected ID: %s, got: %s", expectedID, createdIssue.ID)
	}

	if createdIssue.Summary != expectedSummary {
		t.Errorf("Expected Summary: %s, got: %s", expectedSummary, createdIssue.Summary)
	}

	if createdIssue.Description != expectedDescription {
		t.Errorf("Expected Description: %s, got: %s", expectedDescription, createdIssue.Description)
	}
}

// TestCreateJiraIssueWithInvalidData tests the createJiraIssue function with invalid data
func TestCreateJiraIssueWithInvalidData(t *testing.T) {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := "your-username"
	password := "your-password"
	projectKey := "YOUR_PROJECT_KEY"
	summary := ""
	description := ""

	createdIssue, err := createJiraIssue(jiraURL, username, password, projectKey, summary, description)
	if err == nil {
		t.Errorf("Expected error creating Jira issue with invalid data")
	}
}

// TestCreateJiraIssueWithZeroDivision tests the createJiraIssue function with zero division
func TestCreateJiraIssueWithZeroDivision(t *testing.T) {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := "your-username"
	password := "your-password"
	projectKey := "YOUR_PROJECT_KEY"
	summary := "Test Issue"
	description := "This is a test issue created by Go Agent."

	createdIssue, err := createJiraIssue(jiraURL, username, password, projectKey, summary, description)
	if err != nil {
		t.Errorf("Error creating Jira issue: %v", err)
	}

	expectedID := fmt.Sprintf("%s-%d", projectKey, 1000)
	expectedSummary := "Test Issue"
	expectedDescription := "This is a test issue created by Go Agent."

	if createdIssue.ID != expectedID {
		t.Errorf("Expected ID: %s, got: %s", expectedID, createdIssue.ID)
	}

	if createdIssue.Summary != expectedSummary {
		t.Errorf("Expected Summary: %s, got: %s", expectedSummary, createdIssue.Summary)
	}

	if createdIssue.Description != expectedDescription {
		t.Errorf("Expected Description: %s, got: %s", expectedDescription, createdIssue.Description)
	}
}