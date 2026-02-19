package main

import (
	"fmt"
	"net/http"
)

// JiraClient representa a interface para interagir com o Jira API
type JiraClient struct {
	baseURL string
	token    string
}

// NewJiraClient cria uma nova instância de JiraClient
func NewJiraClient(baseURL, token string) *JiraClient {
	return &JiraClient{
		baseURL: baseURL,
		token:    token,
	}
}

// CreateIssue cria um novo issue no Jira
func (jc *JiraClient) CreateIssue(title, description string) error {
	url := fmt.Sprintf("%s/rest/api/2.0/issue", jc.baseURL)
	reqBody := fmt.Sprintf(`{
		"fields": {
			"title": "%s",
			"description": "%s"
		}
	}`, title, description)

	req, err := http.NewRequest("POST", url, strings.NewReader(reqBody))
	if err != nil {
		return err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", jc.token))

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("failed to create issue: %s", resp.Status)
	}

	fmt.Println("Issue created successfully")
	return nil
}

// main é a função principal do programa
func main() {
	jiraClient := NewJiraClient("https://your-jira-instance.atlassian.net/rest/api/2.0/", "your-jira-token")

	err := jiraClient.CreateIssue("Test Issue", "This is a test issue created by Go Agent.")
	if err != nil {
		fmt.Println(err)
		return
	}
}