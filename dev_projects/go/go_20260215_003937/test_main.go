package main

import (
	"testing"
)

// TestNewJiraClient tests the NewJiraClient function
func TestNewJiraClient(t *testing.T) {
	jc := NewJiraClient("https://your-jira-instance.atlassian.net/rest/api/2.0/", "your-jira-token")
	if jc == nil {
		t.Errorf("NewJiraClient returned nil")
	}
}

// TestCreateIssue tests the CreateIssue function
func TestCreateIssue(t *testing.T) {
	jc := NewJiraClient("https://your-jira-instance.atlassian.net/rest/api/2.0/", "your-jira-token")

	title := "Test Issue"
	description := "This is a test issue created by Go Agent."

	err := jc.CreateIssue(title, description)
	if err != nil {
		t.Errorf("CreateIssue failed: %s", err)
	}
}

// TestCreateIssueError tests the CreateIssue function with an error
func TestCreateIssueError(t *testing.T) {
	jc := NewJiraClient("https://your-jira-instance.atlassian.net/rest/api/2.0/", "your-jira-token")

	title := ""
	description := ""

	err := jc.CreateIssue(title, description)
	if err == nil {
		t.Errorf("CreateIssue did not return an error")
	}
}

// TestCreateIssueEdgeCase tests the CreateIssue function with edge cases
func TestCreateIssueEdgeCase(t *testing.T) {
	jc := NewJiraClient("https://your-jira-instance.atlassian.net/rest/api/2.0/", "your-jira-token")

	title := "Test Issue"
	description := ""

	err := jc.CreateIssue(title, description)
	if err != nil {
		t.Errorf("CreateIssue did not return an error")
	}
}