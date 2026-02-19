package main

import (
	"fmt"
	"net/http"
)

// JiraAPI é a interface para interagir com o API do Jira
type JiraAPI interface {
	CreateIssue(title, description string) error
}

// JiraClient é uma implementação da interface JiraAPI usando HTTP
type JiraClient struct {
	client *http.Client
}

// NewJiraClient cria um novo cliente de Jira
func NewJiraClient(baseURL string) (*JiraClient, error) {
	client := &http.Client{}
	return &JiraClient{client}, nil
}

// CreateIssue implementa a interface JiraAPI para criar um issue no Jira
func (j *JiraClient) CreateIssue(title, description string) error {
	url := fmt.Sprintf("%s/rest/api/2/issue", j.client.BaseURL)
	req, err := http.NewRequest("POST", url, nil)
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Basic <your-base64-encoded-auth-token>")

	body := fmt.Sprintf(`{
		"fields": {
			"project": {"key": "<your-project-key>"},
			"summary": "%s",
			"description": "%s"
		}
	}`, title, description)

	req.Body = strings.NewReader(body)
	resp, err := j.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("failed to create issue: %s", resp.Status)
	}

	return nil
}

// main é o ponto de entrada do programa
func main() {
	jiraClient, err := NewJiraClient("https://your-jira-instance.atlassian.net")
	if err != nil {
		fmt.Println("Error creating Jira client:", err)
		return
	}

	err = jiraClient.CreateIssue("Test Issue", "This is a test issue created by Go Agent.")
	if err != nil {
		fmt.Println("Error creating issue:", err)
		return
	}
	fmt.Println("Issue created successfully!")
}