package main

import (
	"fmt"
	"net/http"
)

// JiraClient representa a interface para interagir com o Jira API
type JiraClient struct {
	client *http.Client
}

// NewJiraClient cria uma nova instância do JiraClient
func NewJiraClient() *JiraClient {
	return &JiraClient{
		client: http.DefaultClient,
	}
}

// CreateIssue cria um novo issue no Jira
func (j *JiraClient) CreateIssue(projectKey, summary string) (*http.Response, error) {
	url := fmt.Sprintf("https://your-jira-instance.atlassian.net/rest/api/2/project/%s/issue", projectKey)
	req, err := http.NewRequest(http.MethodPost, url, nil)
	if err != nil {
		return nil, err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Basic your-jira-token")

	body := fmt.Sprintf(`{
		"fields": {
			"project": {"key": "%s"},
			"summary": "%s",
			"description": "This is a test issue created by Go Agent"
		}
	}`, projectKey, summary)

	req.Body = strings.NewReader(body)
	resp, err := j.client.Do(req)
	if err != nil {
		return nil, err
	}

	return resp, nil
}

// main é o ponto de entrada do programa
func main() {
	jiraClient := NewJiraClient()

	projectKey := "YOUR_PROJECT_KEY"
	summary := "Test Issue"

	resp, err := jiraClient.CreateIssue(projectKey, summary)
	if err != nil {
		fmt.Println("Error creating issue:", err)
		return
	}

	defer resp.Body.Close()

	fmt.Println("Response status code:", resp.StatusCode)
}