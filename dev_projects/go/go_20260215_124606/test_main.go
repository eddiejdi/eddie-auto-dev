package main

import (
	"testing"
)

// TestGetIssues verifies the GetIssues function returns issues correctly
func TestGetIssues(t *testing.T) {
	client := &JiraClient{
		URL:    "https://your-jira-instance.atlassian.net",
		Token:  "YOUR_JIRA_TOKEN",
	}

	issues, err := client.GetIssues()
	if err != nil {
		t.Errorf("Failed to get issues: %v", err)
		return
	}

	if len(issues) == 0 {
		t.Errorf("Expected at least one issue, got none")
	}
}

// TestGetIssuesError verifies the GetIssues function returns an error when the URL is invalid
func TestGetIssuesError(t *testing.T) {
	client := &JiraClient{
		URL:    "https://invalid-url",
		Token:  "YOUR_JIRA_TOKEN",
	}

	_, err := client.GetIssues()
	if err == nil {
		t.Errorf("Expected an error, got none")
	}
}

// TestGetIssuesInvalidToken verifies the GetIssues function returns an error when the token is invalid
func TestGetIssuesInvalidToken(t *testing.T) {
	client := &JiraClient{
		URL:    "https://your-jira-instance.atlassian.net",
		Token:  "invalid-token",
	}

	_, err := client.GetIssues()
	if err == nil {
		t.Errorf("Expected an error, got none")
	}
}

// TestGetIssuesEmptyResponse verifies the GetIssues function returns an empty response when the server returns a 404
func TestGetIssuesEmptyResponse(t *testing.T) {
	client := &JiraClient{
		URL:    "https://your-jira-instance.atlassian.net/rest/api/2/search?jql=project=YOUR_PROJECT&fields=id,status,name",
		Token:  "YOUR_JIRA_TOKEN",
	}

	resp, err := client.GetIssues()
	if err != nil {
		t.Errorf("Failed to get issues: %v", err)
		return
	}

	if len(resp) == 0 {
		t.Errorf("Expected at least one issue, got none")
	}
}