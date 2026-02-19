package main

import (
	"fmt"
	"net/http"
	"testing"
)

// TestNewJiraClient ensures NewJiraClient initializes correctly with provided URL and token.
func TestNewJiraClient(t *testing.T) {
	jc := NewJiraClient("https://your-jira-instance.atlassian.net/rest/api/2/", "YOUR_JIRA_TOKEN")
	if jc.url != "https://your-jira-instance.atlassian.net/rest/api/2/" || jc.token != "YOUR_JIRA_TOKEN" {
		t.Errorf("NewJiraClient should initialize with the provided URL and token, but got %s and %s", jc.url, jc.token)
	}
}

// TestCreateIssue ensures CreateIssue creates an issue successfully.
func TestCreateIssue(t *testing.T) {
	jc := NewJiraClient("https://your-jira-instance.atlassian.net/rest/api/2/", "YOUR_JIRA_TOKEN")
	err := jc.CreateIssue("My New Issue", "This is a test issue created by Go Agent.")
	if err != nil {
		t.Errorf("CreateIssue should create an issue successfully, but got error: %v", err)
	}
}

// TestCreateIssueWithInvalidSummary ensures CreateIssue fails with invalid summary.
func TestCreateIssueWithInvalidSummary(t *testing.T) {
	jc := NewJiraClient("https://your-jira-instance.atlassian.net/rest/api/2/", "YOUR_JIRA_TOKEN")
	err := jc.CreateIssue("", "This is a test issue created by Go Agent.")
	if err == nil {
		t.Errorf("CreateIssue should fail with invalid summary, but got no error")
	}
}

// TestCreateIssueWithInvalidDescription ensures CreateIssue fails with invalid description.
func TestCreateIssueWithInvalidDescription(t *testing.T) {
	jc := NewJiraClient("https://your-jira-instance.atlassian.net/rest/api/2/", "YOUR_JIRA_TOKEN")
	err := jc.CreateIssue("My New Issue", "")
	if err == nil {
		t.Errorf("CreateIssue should fail with invalid description, but got no error")
	}
}

// TestCreateIssueWithInvalidURL ensures CreateIssue fails with invalid URL.
func TestCreateIssueWithInvalidURL(t *testing.T) {
	jc := NewJiraClient("", "YOUR_JIRA_TOKEN")
	err := jc.CreateIssue("My New Issue", "This is a test issue created by Go Agent.")
	if err == nil {
		t.Errorf("CreateIssue should fail with invalid URL, but got no error")
	}
}

// TestCreateIssueWithInvalidToken ensures CreateIssue fails with invalid token.
func TestCreateIssueWithInvalidToken(t *testing.T) {
	jc := NewJiraClient("https://your-jira-instance.atlassian.net/rest/api/2/", "")
	err := jc.CreateIssue("My New Issue", "This is a test issue created by Go Agent.")
	if err == nil {
		t.Errorf("CreateIssue should fail with invalid token, but got no error")
	}
}

// TestCreateIssueWithInvalidRequest ensures CreateIssue fails with invalid request.
func TestCreateIssueWithInvalidRequest(t *testing.T) {
	jc := NewJiraClient("https://your-jira-instance.atlassian.net/rest/api/2/", "YOUR_JIRA_TOKEN")
	req, err := http.NewRequest("POST", "https://invalid-url.com", strings.NewReader(fmt.Sprintf(`{
		"fields": {
			"project": {"key": "YOUR_PROJECT_KEY"},
			"summary": "%s",
			"description": "%s"
		}
	}`, "My New Issue", "This is a test issue created by Go Agent.")))
	if err != nil {
		t.Errorf("NewJiraClient should initialize with the provided URL and token, but got %v", jc.url)
	}

	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", jc.token))
	req.Header.Set("Content-Type", "application/json")

	resp, err := jc.client.Do(req)
	if err != nil {
		t.Errorf("CreateIssue should create an issue successfully, but got error: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusCreated {
		t.Errorf("CreateIssue should fail with invalid request, but got status code %d", resp.StatusCode)
	}
}