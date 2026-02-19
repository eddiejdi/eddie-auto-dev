package main

import (
	"fmt"
	"net/http"
)

// JiraClient representa a interface para interagir com o Jira API
type JiraClient struct {
	url string
}

// NewJiraClient cria uma nova instância de JiraClient
func NewJiraClient(url string) *JiraClient {
	return &JiraClient{url: url}
}

// CreateIssue cria um novo issue no Jira
func (jc *JiraClient) CreateIssue(title, description string) error {
	issue := fmt.Sprintf(`{
		"fields": {
			"project": {"key": "YOUR_PROJECT_KEY"},
			"summary": "%s",
			"description": "%s"
		}
	}`, title, description)

	req, err := http.NewRequest("POST", jc.url+"/rest/api/2/issue", strings.NewReader(issue))
	if err != nil {
		return err
	}

	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("Failed to create issue: %s", resp.Status)
	}

	fmt.Println("Issue created successfully")
	return nil
}

// main é a função principal do programa
func main() {
	jiraClient := NewJiraClient("https://your-jira-instance.atlassian.net")

	title := "New Go Agent Integration"
	description := "Integrating Go Agent with Jira for tracking activities"

	if err := jiraClient.CreateIssue(title, description); err != nil {
		fmt.Println(err)
	}
}

// TestCreateIssueSuccess tests CreateIssue function with valid input
func TestCreateIssueSuccess(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-instance.atlassian.net")
	title := "New Go Agent Integration"
	description := "Integrating Go Agent with Jira for tracking activities"

	err := jiraClient.CreateIssue(title, description)
	if err != nil {
		t.Errorf("CreateIssue should not return an error: %v", err)
	}
}

// TestCreateIssueError tests CreateIssue function with invalid input
func TestCreateIssueError(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-instance.atlassian.net")
	title := "New Go Agent Integration"
	description := ""

	err := jiraClient.CreateIssue(title, description)
	if err == nil {
		t.Errorf("CreateIssue should return an error: %v", err)
	}
}

// TestCreateIssueEdgeCases tests CreateIssue function with edge cases
func TestCreateIssueEdgeCases(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-instance.atlassian.net")
	title := "New Go Agent Integration"
	description := ""

	err := jiraClient.CreateIssue(title, description)
	if err == nil {
		t.Errorf("CreateIssue should return an error: %v", err)
	}
}