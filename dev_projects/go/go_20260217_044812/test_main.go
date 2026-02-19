package main_test

import (
	"testing"
)

// TestCreateJiraIssue tests the createJiraIssue function with valid inputs
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

	expectedSummary := fmt.Sprintf("%s-%s", projectKey, summary)
	expectedDescription := description

	if createdIssue.Key != expectedSummary {
		t.Errorf("Expected key to be %s, got %s", expectedSummary, createdIssue.Key)
	}
	if createdIssue.Description != expectedDescription {
		t.Errorf("Expected description to be %s, got %s", expectedDescription, createdIssue.Description)
	}

	fmt.Printf("Created Issue: %+v\n", createdIssue)
}

// TestCreateJiraIssueError tests the createJiraIssue function with invalid inputs
func TestCreateJiraIssueError(t *testing.T) {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := "your-username"
	password := "your-password"
	projectKey := "YOUR_PROJECT_KEY"
	summary := ""
	description := ""

	_, err := createJiraIssue(jiraURL, username, password, projectKey, summary, description)
	if err == nil {
		t.Errorf("Expected error creating Jira issue with invalid inputs")
	}
}

// TestCreateJiraIssueEdgeCases tests the createJiraIssue function with edge cases
func TestCreateJiraIssueEdgeCases(t *testing.T) {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := "your-username"
	password := "your-password"
	projectKey := ""
	summary := "Test Issue"
	description := ""

	_, err := createJiraIssue(jiraURL, username, password, projectKey, summary, description)
	if err == nil {
		t.Errorf("Expected error creating Jira issue with empty project key")
	}
}

// TestCreateJiraIssueEdgeCases tests the createJiraIssue function with edge cases
func TestCreateJiraIssueEdgeCases(t *testing.T) {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := "your-username"
	password := ""
	projectKey := "YOUR_PROJECT_KEY"
	summary := "Test Issue"
	description := ""

	_, err := createJiraIssue(jiraURL, username, password, projectKey, summary, description)
	if err == nil {
		t.Errorf("Expected error creating Jira issue with empty summary")
	}
}

// TestCreateJiraIssueEdgeCases tests the createJiraIssue function with edge cases
func TestCreateJiraIssueEdgeCases(t *testing.T) {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := ""
	password := ""
	projectKey := "YOUR_PROJECT_KEY"
	summary := "Test Issue"
	description := ""

	_, err := createJiraIssue(jiraURL, username, password, projectKey, summary, description)
	if err == nil {
		t.Errorf("Expected error creating Jira issue with empty password")
	}
}

// TestCreateJiraIssueEdgeCases tests the createJiraIssue function with edge cases
func TestCreateJiraIssueEdgeCases(t *testing.T) {
	jiraURL := ""
	username := "your-username"
	password := "your-password"
	projectKey := "YOUR_PROJECT_KEY"
	summary := "Test Issue"
	description := ""

	_, err := createJiraIssue(jiraURL, username, password, projectKey, summary, description)
	if err == nil {
		t.Errorf("Expected error creating Jira issue with empty jira URL")
	}
}