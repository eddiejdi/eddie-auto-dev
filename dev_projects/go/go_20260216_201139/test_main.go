package main_test

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestCreateJiraIssue(t *testing.T) {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := "your-username"
	password := "your-password"
	projectKey := "YOUR_PROJECT_KEY"
	summary := "Test Issue"
	description := "This is a test issue created by Go Agent."

	testCases := []struct {
		name        string
		jiraURL     string
		username    string
		password    string
		projectKey  string
		summary      string
		description string
	}{
		{"Success", jiraURL, username, password, projectKey, summary, description},
		{"Invalid URL", "https://invalid-url.atlassian.net/rest/api/2/issue", username, password, projectKey, summary, description},
		{"Missing Username", jiraURL, "", password, projectKey, summary, description},
		{"Missing Password", jiraURL, username, "", projectKey, summary, description},
		{"Invalid Project Key", jiraURL, username, password, "INVALID_PROJECT_KEY", summary, description},
		{"Empty Summary", jiraURL, username, password, projectKey, "", description},
		{"Empty Description", jiraURL, username, password, projectKey, summary, ""},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			createdIssue, err := createJiraIssue(tc.jiraURL, tc.username, tc.password, tc.projectKey, tc.summary, tc.description)
			if err != nil {
				assert.Error(t, err)
				return
			}

			assert.NotEmpty(t, createdIssue.ID)
			assert.NotEmpty(t, createdIssue.Key)
			assert.NotEmpty(t, createdIssue.Summary)
			assert.NotEmpty(t, createdIssue.Description)
		})
	}
}