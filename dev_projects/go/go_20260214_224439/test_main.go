package main

import (
	"testing"
)

// TestJiraClientCreateIssue tests the CreateIssue method of JiraClient
func TestJiraClientCreateIssue(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-url.com/rest/api/2/", "your-jira-token")

	err := jiraClient.CreateIssue("Bug in Go Agent", "Go Agent is not working as expected")
	if err != nil {
		t.Errorf("CreateIssue should not return an error, but got: %v", err)
	}
}

// TestJiraClientUpdateIssue tests the UpdateIssue method of JiraClient
func TestJiraClientUpdateIssue(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-url.com/rest/api/2/", "your-jira-token")

	err := jiraClient.UpdateIssue(123, "Bug in Go Agent", "Go Agent is now working properly")
	if err != nil {
		t.Errorf("UpdateIssue should not return an error, but got: %v", err)
	}
}

// TestJiraClientCreateIssueError tests the CreateIssue method with an error
func TestJiraClientCreateIssueError(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-url.com/rest/api/2/", "your-jira-token")

	err := jiraClient.CreateIssue("", "")
	if err == nil {
		t.Errorf("CreateIssue should return an error, but got: %v", err)
	}
}

// TestJiraClientUpdateIssueError tests the UpdateIssue method with an error
func TestJiraClientUpdateIssueError(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-url.com/rest/api/2/", "your-jira-token")

	err := jiraClient.UpdateIssue(0, "", "")
	if err == nil {
		t.Errorf("UpdateIssue should return an error, but got: %v", err)
	}
}

// TestJiraClientCreateIssueEdgeCase tests the CreateIssue method with edge cases
func TestJiraClientCreateIssueEdgeCase(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-url.com/rest/api/2/", "your-jira-token")

	err := jiraClient.CreateIssue("Bug in Go Agent", "")
	if err == nil {
		t.Errorf("CreateIssue should return an error, but got: %v", err)
	}

	err = jiraClient.CreateIssue("", "Go Agent is not working as expected")
	if err == nil {
		t.Errorf("CreateIssue should return an error, but got: %v", err)
	}
}