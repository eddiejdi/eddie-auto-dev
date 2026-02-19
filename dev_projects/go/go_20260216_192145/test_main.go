package main_test

import (
	"bytes"
	"encoding/json"
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
			name: "Failure with invalid input (project key is empty)",
			input: struct {
				jiraURL, username, password, projectKey, summary, description string
			}{
				jiraURL,
				username,
				password,
				"",
				summary,
				description,
			},
			expected: fmt.Errorf("Error creating Jira issue: Project key cannot be empty"),
		},
		{
			name: "Failure with invalid input (summary is empty)",
			input: struct {
				jiraURL, username, password, projectKey, summary, description string
			}{
				jiraURL,
				username,
				password,
				projectKey,
				"",
				description,
			},
			expected: fmt.Errorf("Error creating Jira issue: Summary cannot be empty"),
		},
		{
			name: "Failure with invalid input (description is empty)",
			input: struct {
				jiraURL, username, password, projectKey, summary, description string
			}{
				jiraURL,
				username,
				password,
				projectKey,
				summary,
				"",
			},
			expected: fmt.Errorf("Error creating Jira issue: Description cannot be empty"),
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			req, err := http.NewRequest("POST", tc.input.jiraURL, strings.NewReader(fmt.Sprintf(`{
				"fields": {
					"project": {"key": "%s"},
					"summary": "%s",
					"description": "%s"
				}
			}`, tc.input.projectKey, tc.input.summary, tc.input.description)))
			if err != nil {
				t.Errorf("Error creating request: %v", err)
				return
			}
			req.Header.Set("Content-Type", "application/json")
			req.Header.Set("Authorization", fmt.Sprintf("Basic %s", base64.StdEncoding.EncodeToString([]byte(fmt.Sprintf("%s:%s", tc.input.username, tc.input.password)))))

			resp, err := http.Client().Do(req)
			if err != nil {
				t.Errorf("Error sending request: %v", err)
				return
			}
			defer resp.Body.Close()

			bodyBytes, err := ioutil.ReadAll(resp.Body)
			if err != nil {
				t.Errorf("Error reading response body: %v", err)
				return
			}

			var issue JiraIssue
			err = json.Unmarshal(bodyBytes, &issue)
			if err != nil {
				t.Errorf("Error parsing JSON response: %v", err)
				return
			}
			defer resp.Body.Close()

			assert.Equal(t, tc.expected, err)
		})
	}
}