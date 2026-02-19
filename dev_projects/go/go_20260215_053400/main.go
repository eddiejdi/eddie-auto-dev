package main

import (
	"fmt"
	"net/http"
)

// JiraClient representa a interface para interagir com o Jira API.
type JiraClient struct {
	baseURL string
}

// NewJiraClient cria uma nova instância de JiraClient.
func NewJiraClient(baseURL string) *JiraClient {
	return &JiraClient{
		baseURL: baseURL,
	}
}

// CreateIssue cria um novo issue no Jira.
func (j *JiraClient) CreateIssue(summary, description string) error {
	url := fmt.Sprintf("%s/rest/api/2/issue", j.baseURL)
	reqBody := fmt.Sprintf(`{
		"fields": {
			"summary": "%s",
			"description": "%s"
		}
	}`, summary, description)

	resp, err := http.Post(url, "application/json", strings.NewReader(reqBody))
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("failed to create issue: %d", resp.StatusCode)
	}

	fmt.Println("Issue created successfully")
	return nil
}

// main é a função principal do programa.
func main() {
	client := NewJiraClient("https://your-jira-instance.atlassian.net")

	err := client.CreateIssue("Bug in Go Agent", "Go Agent is not working as expected.")
	if err != nil {
		fmt.Println(err)
		return
	}
}