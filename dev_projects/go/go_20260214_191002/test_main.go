package main

import (
	"testing"
	"net/http"
	"encoding/json"
)

// TestJiraAPICreateJiraAPIClient tests the CreateJiraAPIClient function
func TestJiraAPICreateJiraAPIClient(t *testing.T) {
	jira := CreateJiraAPIClient("https://your-jira-instance.atlassian.net")
	if jira == nil {
		t.Errorf("CreateJiraAPIClient returned nil")
	}
}

// TestJiraAPIGetIssue tests the GetIssue function
func TestJiraAPIGetIssue(t *testing.T) {
	jira := CreateJiraAPIClient("https://your-jira-instance.atlassian.net")

	resp, err := jira.GetIssue("12345")
	if err != nil {
		t.Errorf("GetIssue failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Errorf("GetIssue returned status code %d", resp.StatusCode)
	}
}

// TestJiraAPIUpdateIssue tests the UpdateIssue function
func TestJiraAPIUpdateIssue(t *testing.T) {
	jira := CreateJiraAPIClient("https://your-jira-instance.atlassian.net")

	payload := map[string]interface{}{
		"fields": map[string]interface{}{
			"description": "Updated issue description",
		},
	}

	resp, err := jira.UpdateIssue("12345", payload)
	if err != nil {
		t.Errorf("UpdateIssue failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Errorf("UpdateIssue returned status code %d", resp.StatusCode)
	}
}

// TestJiraAPIInvalidBaseURL tests the CreateJiraAPIClient function with an invalid base URL
func TestJiraAPIInvalidBaseURL(t *testing.T) {
	jira := CreateJiraAPIClient("http://invalid-url")
	if jira != nil {
		t.Errorf("CreateJiraAPIClient returned a valid instance for an invalid base URL")
	}
}

// TestJiraAPIEmptyIssueID tests the GetIssue function with an empty issue ID
func TestJiraAPIEmptyIssueID(t *testing.T) {
	jira := CreateJiraAPIClient("https://your-jira-instance.atlassian.net")

	resp, err := jira.GetIssue("")
	if err != nil {
		t.Errorf("GetIssue failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusNotFound {
		t.Errorf("GetIssue returned status code %d for an empty issue ID", resp.StatusCode)
	}
}

// TestJiraAPIInvalidPayload tests the UpdateIssue function with an invalid payload
func TestJiraAPIInvalidPayload(t *testing.T) {
	jira := CreateJiraAPIClient("https://your-jira-instance.atlassian.net")

	payload := map[string]interface{}{
		"fields": map[string]interface{}{
			"description": "Updated issue description",
		},
	}

	resp, err := jira.UpdateIssue("12345", nil)
	if err != nil {
		t.Errorf("UpdateIssue failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusBadRequest {
		t.Errorf("UpdateIssue returned status code %d for an invalid payload", resp.StatusCode)
	}
}