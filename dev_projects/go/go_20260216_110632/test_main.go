package main

import (
	"testing"
)

// TestJiraClientGetIssue tests the GetIssue method of JiraClient
func TestJiraClientGetIssue(t *testing.T) {
	jc := &JiraClient{
		URL:    "https://your-jira-instance.atlassian.net",
		Token:  "your-jira-token",
	}

	resp, err := jc.GetIssue("ABC-123")
	if err != nil {
		t.Errorf("GetIssue failed with error: %v", err)
	}
	if resp.StatusCode != http.StatusOK {
		t.Errorf("Expected status code 200, got %d", resp.StatusCode)
	}
}

// TestJiraClientLogIssue tests the LogIssue method of JiraClient
func TestJiraClientLogIssue(t *testing.T) {
	jc := &JiraClient{
		URL:    "https://your-jira-instance.atlassian.net",
		Token:  "your-jira-token",
	}

	err := jc.LogIssue("ABC-123")
	if err != nil {
		t.Errorf("LogIssue failed with error: %v", err)
	}
}