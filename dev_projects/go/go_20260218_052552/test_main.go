package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"strings"

	"github.com/stretchr/testify/assert"
)

// JiraIssue represents a Jira issue
type JiraIssue struct {
	ID        string `json:"id"`
	Key       string `json:"key"`
	Summary   string `json:"summary"`
	Description string `json:"description"`
}

func createJiraIssue(jiraURL, username, password, projectKey, summary, description string) (*JiraIssue, error) {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	body := fmt.Sprintf(`{
		"fields": {
			"project": {"key": "%s"},
			"summary": "%s",
			"description": "%s"
		}
	}`, projectKey, summary, description)

	req, err := http.NewRequest("POST", jiraURL, strings.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("Error creating request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Basic %s", base64.StdEncoding.EncodeToString([]byte(fmt.Sprintf("%s:%s", username, password)))))

	resp, err := http.Client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("Error sending request: %v", err)
	}
	defer resp.Body.Close()

	bodyBytes, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("Error reading response body: %v", err)
	}

	var issue JiraIssue
	err = json.Unmarshal(bodyBytes, &issue)
	if err != nil {
		return nil, fmt.Errorf("Error parsing JSON response: %v", err)
	}
	defer resp.Body.Close()

	return &issue, nil
}

func main() {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := "your-username"
	password := "your-password"
	projectKey := "YOUR_PROJECT_KEY"
	summary := "Test Issue"
	description := "This is a test issue created by Go Agent."

	// Test cases for createJiraIssue function
	testCases := []struct {
		name     string
		input    struct {
			jiraURL, username, password, projectKey, summary, description string
		}
		expected *JiraIssue
	}{
		{
			name: "Success case with valid inputs",
			input: struct {
				jiraURL, username, password, projectKey, summary, description string
			}{
				jiraURL:    jiraURL,
				username:   username,
				password:  password,
				projectKey: projectKey,
				summary:   summary,
				description: description,
			},
			expected: &JiraIssue{
				ID:        "123456789",
				Key:       "TEST-1",
				Summary:   summary,
				Description: description,
			},
		},
		{
			name: "Error case with invalid inputs (empty summary)",
			input: struct {
				jiraURL, username, password, projectKey, summary, description string
			}{
				jiraURL:    jiraURL,
				username:   username,
				password:  password,
				projectKey: projectKey,
				summary:   "",
				description: description,
			},
			expected: nil,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			createdIssue, err := createJiraIssue(tc.input.jiraURL, tc.input.username, tc.input.password, tc.input.projectKey, tc.input.summary, tc.input.description)
			if err != nil && tc.expected == nil {
				assert.NoError(t, err)
			} else if err == nil && tc.expected != nil {
				assert.Equal(t, *createdIssue, *tc.expected)
			}
		})
	}
}