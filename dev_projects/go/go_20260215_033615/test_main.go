package main_test

import (
	"encoding/json"
	"fmt"
	"net/http"
	"testing"

	"github.com/stretchr/testify/assert"
)

// TestNewJiraClient verifies the NewJiraClient function
func TestNewJiraClient(t *testing.T) {
	client := NewJiraClient("https://your-jira-instance.atlassian.net", "your-api-token")
	assert.NotNil(t, client)
}

// TestGetIssues verifies the GetIssues function
func TestGetIssues(t *testing.T) {
	client := NewJiraClient("https://your-jira-instance.atlassian.net", "your-api-token")

	query := "project=YOUR_PROJECT AND status IN (OPEN, IN_PROGRESS)"
	issues, err := client.GetIssues(query)
	assert.NoError(t, err)

	expectedIssue := map[string]interface{}{
		"id":    "12345",
		"fields": map[string]interface{}{
			"summary":  "Test Issue",
			"status":   "OPEN",
			"description": "",
		},
	}
	foundIssue := false
	for _, issue := range issues {
		if fmt.Sprintf("%v", issue) == fmt.Sprintf("%+v", expectedIssue) {
			foundIssue = true
			break
		}
	}
	assert.True(t, foundIssue)
}

// TestGetIssuesError verifies the GetIssues function with an error
func TestGetIssuesError(t *testing.T) {
	client := NewJiraClient("https://your-jira-instance.atlassian.net", "your-api-token")

	query := "project=INVALID_PROJECT AND status IN (OPEN, IN_PROGRESS)"
	issues, err := client.GetIssues(query)
	assert.Error(t, err)
}

// TestGetIssuesEdgeCase verifies the GetIssues function with an edge case
func TestGetIssuesEdgeCase(t *testing.T) {
	client := NewJiraClient("https://your-jira-instance.atlassian.net", "your-api-token")

	query := ""
	issues, err := client.GetIssues(query)
	assert.NoError(t, err)

	expectedIssue := map[string]interface{}{
		"id":    "",
		"fields": map[string]interface{}{
			"summary":  "",
			"status":   "",
			"description": "",
		},
	}
	foundIssue := false
	for _, issue := range issues {
		if fmt.Sprintf("%v", issue) == fmt.Sprintf("%+v", expectedIssue) {
			foundIssue = true
			break
		}
	}
	assert.True(t, foundIssue)
}