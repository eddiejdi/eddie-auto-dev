package main

import (
	"testing"
)

// TestNewJiraClient tests the NewJiraClient function
func TestNewJiraClient(t *testing.T) {
	jc, err := NewJiraClient("https://your-jira-instance.atlassian.net", "your-jira-token")
	if err != nil {
		t.Errorf("Error creating Jira client: %s", err)
	}
}

// TestCreateIssue tests the CreateIssue function
func TestCreateIssue(t *testing.T) {
	jc, err := NewJiraClient("https://your-jira-instance.atlassian.net", "your-jira-token")
	if err != nil {
		t.Errorf("Error creating Jira client: %s", err)
	}

	title := "New Test Issue"
	description := "This is a test issue created using Go Agent with Jira."

	resp, err := jc.CreateIssue(title, description)
	if err != nil {
		t.Errorf("Error creating issue: %s", err)
	}
	defer resp.Body.Close()

	if resp.Status != http.StatusOK {
		t.Errorf("Expected status code 201, got %d", resp.Status)
	}

	// Additional assertions can be added here to check the response body or other aspects of the response
}