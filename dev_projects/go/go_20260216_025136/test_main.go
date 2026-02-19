package main

import (
	"fmt"
	"log"
	"net/http"
	"strings"

	"github.com/stretchr/testify/assert"
)

// JiraClient representa a interface para interagir com o API do Jira
type JiraClient struct {
	URL string
}

// NewJiraClient cria uma nova instância de JiraClient
func NewJiraClient(url string) *JiraClient {
	return &JiraClient{URL: url}
}

// CreateIssue cria um novo issue no Jira
func (j *JiraClient) CreateIssue(title, description string) error {
	reqBody := fmt.Sprintf(`{
		"fields": {
			"project": {"key": "YOUR_PROJECT_KEY"},
			"summary": "%s",
			"description": "%s"
		}
	}`, title, description)

	resp, err := http.Post(j.URL+"/rest/api/2/issue", "application/json", strings.NewReader(reqBody))
	if err != nil {
		return fmt.Errorf("Failed to create issue: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("Failed to create issue, status code: %d", resp.StatusCode)
	}

	fmt.Println("Issue created successfully")
	return nil
}

// main é a função principal do programa
func main() {
	jiraClient := NewJiraClient("https://your-jira-instance.atlassian.net")

	title := "Test Issue"
	description := "This is a test issue for the Go Agent integration."

	err := jiraClient.CreateIssue(title, description)
	if err != nil {
		log.Fatalf("Error creating issue: %v", err)
	}
}

// TestCreateIssue tests the CreateIssue function with valid inputs
func TestCreateIssue(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-instance.atlassian.net")

	title := "Test Issue"
	description := "This is a test issue for the Go Agent integration."

	err := jiraClient.CreateIssue(title, description)
	if err != nil {
		t.Errorf("CreateIssue failed: %v", err)
	}
}

// TestCreateIssueWithInvalidTitle tests the CreateIssue function with an invalid title
func TestCreateIssueWithInvalidTitle(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-instance.atlassian.net")

	title := ""
	description := "This is a test issue for the Go Agent integration."

	err := jiraClient.CreateIssue(title, description)
	if err == nil {
		t.Errorf("CreateIssue did not fail with invalid title")
	}
}

// TestCreateIssueWithInvalidDescription tests the CreateIssue function with an invalid description
func TestCreateIssueWithInvalidDescription(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-instance.atlassian.net")

	title := "Test Issue"
	description := ""

	err := jiraClient.CreateIssue(title, description)
	if err == nil {
		t.Errorf("CreateIssue did not fail with invalid description")
	}
}

// TestCreateIssueWithInvalidURL tests the CreateIssue function with an invalid URL
func TestCreateIssueWithInvalidURL(t *testing.T) {
	jiraClient := NewJiraClient("https://invalid-url")

	title := "Test Issue"
	description := "This is a test issue for the Go Agent integration."

	err := jiraClient.CreateIssue(title, description)
	if err == nil {
		t.Errorf("CreateIssue did not fail with invalid URL")
	}
}

// TestCreateIssueWithInvalidRequestBody tests the CreateIssue function with an invalid request body
func TestCreateIssueWithInvalidRequestBody(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-instance.atlassian.net")

	title := "Test Issue"
	description := "This is a test issue for the Go Agent integration."

	reqBody := `{
		"fields": {
			"project": {"key": "YOUR_PROJECT_KEY"},
			"summary": "%s",
			"description": "%s"
		}
	}`

	resp, err := http.Post(jiraClient.URL+"/rest/api/2/issue", "application/json", strings.NewReader(reqBody))
	if err != nil {
		t.Errorf("CreateIssue failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusCreated {
		t.Errorf("CreateIssue did not fail with invalid request body")
	}
}

// TestCreateIssueWithInvalidResponseStatusCode tests the CreateIssue function with an invalid response status code
func TestCreateIssueWithInvalidResponseStatusCode(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-instance.atlassian.net")

	title := "Test Issue"
	description := "This is a test issue for the Go Agent integration."

	reqBody := fmt.Sprintf(`{
		"fields": {
			"project": {"key": "YOUR_PROJECT_KEY"},
			"summary": "%s",
			"description": "%s"
		}
	}`, title, description)

	resp, err := http.Post(jiraClient.URL+"/rest/api/2/issue", "application/json", strings.NewReader(reqBody))
	if err != nil {
		t.Errorf("CreateIssue failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK {
		t.Errorf("CreateIssue did not fail with invalid response status code")
	}
}

// TestCreateIssueWithInvalidResponseContent tests the CreateIssue function with an invalid response content
func TestCreateIssueWithInvalidResponseContent(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-instance.atlassian.net")

	title := "Test Issue"
	description := "This is a test issue for the Go Agent integration."

	reqBody := fmt.Sprintf(`{
		"fields": {
			"project": {"key": "YOUR_PROJECT_KEY"},
			"summary": "%s",
			"description": "%s"
		}
	}`, title, description)

	resp, err := http.Post(jiraClient.URL+"/rest/api/2/issue", "application/json", strings.NewReader(reqBody))
	if err != nil {
		t.Errorf("CreateIssue failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusCreated && resp.ContentLength > 0 {
		t.Errorf("CreateIssue did not fail with invalid response content")
	}
}