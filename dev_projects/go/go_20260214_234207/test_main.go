package main

import (
	"testing"
)

// TestNewJiraClient tests the NewJiraClient function
func TestNewJiraClient(t *testing.T) {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	jiraClient, err := NewJiraClient(url, token)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}
}

// TestCreateIssue tests the CreateIssue function
func TestCreateIssue(t *testing.T) {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	jiraClient, err := NewJiraClient(url, token)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}

	summary := "New Test Case"
	description := "This is a new test case for the Go Agent integration."

	newIssue, err := jiraClient.CreateIssue(summary, description)
	if err != nil {
		t.Errorf("Failed to create issue: %v", err)
	}
}

// TestUpdateIssue tests the UpdateIssue function
func TestUpdateIssue(t *testing.T) {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	jiraClient, err := NewJiraClient(url, token)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}

	summary := "New Test Case"
	description := "This is a new test case for the Go Agent integration."

	newIssue, err := jiraClient.CreateIssue(summary, description)
	if err != nil {
		t.Errorf("Failed to create issue: %v", err)
	}

	fieldsToUpdate := map[string]interface{}{
		"status": "In Progress",
	}
	err = jiraClient.UpdateIssue(newIssue.ID, fieldsToUpdate)
	if err != nil {
		t.Errorf("Failed to update issue: %v", err)
	}
}

// TestDeleteIssue tests the DeleteIssue function
func TestDeleteIssue(t *testing.T) {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	jiraClient, err := NewJiraClient(url, token)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}

	summary := "New Test Case"
	description := "This is a new test case for the Go Agent integration."

	newIssue, err := jiraClient.CreateIssue(summary, description)
	if err != nil {
		t.Errorf("Failed to create issue: %v", err)
	}

	err = jiraClient.DeleteIssue(newIssue.ID)
	if err != nil {
		t.Errorf("Failed to delete issue: %v", err)
	}
}