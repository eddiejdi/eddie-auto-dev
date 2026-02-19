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
		name     string
		input    struct {
			jiraURL, username, password, projectKey, summary, description string
		}
		expected error
	}{
		{
			name: "Success with valid inputs",
			input: struct {
				jiraURL, username, password, projectKey, summary, description string
			}{
				jiraURL,
				username,
				password,
				projectKey,
				summary,
				description,
			},
			expected: nil,
		},
		{
			name: "Error with invalid input",
			input: struct {
				jiraURL, username, password, projectKey, summary, description string
			}{
				jiraURL,
				username,
				password,
				projectKey,
				"invalid summary",
				description,
			},
			expected: fmt.Errorf("Invalid summary"),
		},
		{
			name: "Error with missing input",
			input: struct {
				jiraURL, username, password, projectKey, summary, description string
			}{
				jiraURL,
				username,
				password,
				projectKey,
				summary,
			},
			expected: fmt.Errorf("Missing required field(s)"),
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			createdIssue, err := createJiraIssue(tc.input.jiraURL, tc.input.username, tc.input.password, tc.input.projectKey, tc.input.summary, tc.input.description)
			if !assert.NoError(t, err) {
				return
			}
			assert.NotEmpty(t, createdIssue.ID)
			assert.NotEmpty(t, createdIssue.Key)
			assert.NotEmpty(t, createdIssue.Summary)
			assert.NotEmpty(t, createdIssue.Description)
		})
	}
}