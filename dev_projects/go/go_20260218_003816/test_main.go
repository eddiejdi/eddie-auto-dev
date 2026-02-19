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

func createJiraIssue(jiraURL, username, password, projectKey, summary, description string) (*JiraIssue, error) {
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

	resp, err := http.Client().Do(req)
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

func TestCreateJiraIssue(t *testing.T) {
	testCases := []struct {
		jiraURL    string
		username  string
		password  string
		projectKey string
		summary   string
		description string
	}{
		{
			jiraURL:    "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username:  "your-username",
			password:  "your-password",
			projectKey: "YOUR_PROJECT_KEY",
			summary:   "Test Issue",
			description: "This is a test issue created by Go Agent.",
		},
		// Add more test cases as needed
	}

	for _, tc := range testCases {
		t.Run(fmt.Sprintf("CreateJiraIssue_%s", tc.summary), func(t *testing.T) {
			createdIssue, err := createJiraIssue(tc.jiraURL, tc.username, tc.password, tc.projectKey, tc.summary, tc.description)
			if err != nil {
				t.Errorf("createJiraIssue(%q, %q, %q, %q, %q, %q) = %v; want no error", tc.jiraURL, tc.username, tc.password, tc.projectKey, tc.summary, tc.description, err)
			}
			if createdIssue == nil {
				t.Errorf("createJiraIssue(%q, %q, %q, %q, %q, %q) = nil; want non-nil issue", tc.jiraURL, tc.username, tc.password, tc.projectKey, tc.summary, tc.description)
			}
			// Add more assertions as needed
		})
	}
}