package main_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"testing"

	"github.com/stretchr/testify/assert"
)

// TestNewJiraClient verifies that NewJiraClient initializes the client correctly
func TestNewJiraClient(t *testing.T) {
	client := NewJiraClient()
	assert.NotNil(t, client)
}

// TestCreateIssue verifies that CreateIssue creates a new issue in Jira
func TestCreateIssue(t *testing.T) {
	jiraClient := NewJiraClient()

	projectKey := "YOUR_PROJECT_KEY"
	summary := "Test Issue"

	req, err := http.NewRequest(http.MethodPost, "https://your-jira-instance.atlassian.net/rest/api/2/project/YOUR_PROJECT_KEY/issue", nil)
	if err != nil {
		t.Errorf("Failed to create request: %v", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Basic your-jira-token")

	body := fmt.Sprintf(`{
		"fields": {
			"project": {"key": "%s"},
			"summary": "%s",
			"description": "This is a test issue created by Go Agent"
		}
	}`, projectKey, summary)

	req.Body = strings.NewReader(body)
	resp, err := jiraClient.client.Do(req)
	if err != nil {
		t.Errorf("Failed to send request: %v", err)
	}

	defer resp.Body.Close()

	assert.Equal(t, http.StatusOK, resp.StatusCode)
}

// TestCreateIssueError verifies that CreateIssue returns an error when the project key is invalid
func TestCreateIssueError(t *testing.T) {
	jiraClient := NewJiraClient()

	projectKey := "INVALID_PROJECT_KEY"
	summary := "Test Issue"

	req, err := http.NewRequest(http.MethodPost, "https://your-jira-instance.atlassian.net/rest/api/2/project/YOUR_PROJECT_KEY/issue", nil)
	if err != nil {
		t.Errorf("Failed to create request: %v", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Basic your-jira-token")

	body := fmt.Sprintf(`{
		"fields": {
			"project": {"key": "%s"},
			"summary": "%s",
			"description": "This is a test issue created by Go Agent"
		}
	}`, projectKey, summary)

	req.Body = strings.NewReader(body)
	resp, err := jiraClient.client.Do(req)
	if err != nil {
		t.Errorf("Failed to send request: %v", err)
	}

	defer resp.Body.Close()

	assert.Equal(t, http.StatusBadRequest, resp.StatusCode)
}