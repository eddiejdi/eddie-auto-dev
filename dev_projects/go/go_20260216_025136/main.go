package main

import (
	"fmt"
	"log"
	"net/http"
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