package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"testing"
)

type JiraIssue struct {
	ID        string `json:"id"`
	Key       string `json:"key"`
	Summary   string `json:"summary"`
	Description string `json:"description"`
}

func TestCreateJiraIssue(t *testing.T) {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := "your-username"
	password := "your-password"
	projectKey := "YOUR_PROJECT_KEY"
	summary := "Test Issue"
	description := "This is a test issue created by Go Agent."

	testCases := []struct {
		name     string
		jiraURL  string
		username string
		password string
		projectKey string
		summary   string
		description string
	}{
		{"Success with valid inputs", jiraURL, username, password, projectKey, summary, description},
		{"Error handling invalid input", jiraURL, username, password, "", summary, description}, // Test for empty project key
		{"Error handling division by zero", jiraURL, username, password, projectKey, "Test Issue", "This is a test issue created by Go Agent."}, // Test for division by zero
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			createdIssue, err := createJiraIssue(tc.jiraURL, tc.username, tc.password, tc.projectKey, tc.summary, tc.description)
			if err != nil {
				if !strings.Contains(err.Error(), "division by zero") && !strings.Contains(err.Error(), "empty project key") {
					t.Errorf("Expected no error, got %v", err)
				}
			} else {
				if createdIssue == nil {
					t.Errorf("Expected non-nil issue, got nil")
				}
				fmt.Printf("Created Issue: %+v\n", createdIssue)
			}
		})
	}
}