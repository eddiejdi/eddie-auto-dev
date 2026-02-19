package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"testing"
)

// TestNewJiraClient ensures NewJiraClient returns a non-nil client with the correct base URL.
func TestNewJiraClient(t *testing.T) {
	client, err := NewJiraClient("https://your-jira-instance.atlassian.net")
	if err != nil {
		t.Errorf("Error creating Jira client: %s", err)
	}
	if client == nil {
		t.Errorf("NewJiraClient returned a nil client")
	}
}

// TestCreateIssue ensures CreateIssue creates an issue with the correct fields.
func TestCreateIssue(t *testing.T) {
	client, err := NewJiraClient("https://your-jira-instance.atlassian.net")
	if err != nil {
		t.Errorf("Error creating Jira client: %s", err)
	}

	title := "Test Issue"
	description := "This is a test issue created by Go Agent."
	reqBody := fmt.Sprintf(`{
		"fields": {
			"project": {"key": "<your-project-key>"},
			"summary": "%s",
			"description": "%s"
		}
	}`, title, description)

	resp, err := client.CreateIssue(title, description)
	if err != nil {
		t.Errorf("Error creating issue: %s", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		t.Errorf("Failed to create issue: %s", resp.Status)
	}

	var issue map[string]interface{}
	err = json.NewDecoder(resp.Body).Decode(&issue)
	if err != nil {
		t.Errorf("Error decoding response body: %s", err)
	}

	expectedProjectKey := "<your-project-key>"
	expectedSummary := title
	expectedDescription := description

	if issue["fields"].(map[string]interface{})["project"].(map[string]interface{})["key"] != expectedProjectKey {
		t.Errorf("Expected project key %s, got %s", expectedProjectKey, issue["fields"].(map[string]interface{})["project"].(map[string]interface{})["key"])
	}

	if issue["fields"].(map[string]interface{})["summary"] != expectedSummary {
		t.Errorf("Expected summary %s, got %s", expectedSummary, issue["fields"].(map[string]interface{})["summary"])
	}

	if issue["fields"].(map[string]interface{})["description"] != expectedDescription {
		t.Errorf("Expected description %s, got %s", expectedDescription, issue["fields"].(map[string]interface{})["description"])
	}
}