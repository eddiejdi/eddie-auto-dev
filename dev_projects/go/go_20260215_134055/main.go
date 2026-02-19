package main

import (
	"fmt"
	"net/http"
)

// JiraClient é uma estrutura que representa a conexão com o Jira API
type JiraClient struct {
	url    string
	token  string
	client *http.Client
}

// NewJiraClient cria um novo cliente de Jira
func NewJiraClient(url, token string) (*JiraClient, error) {
	client := &http.Client{}
	return &JiraClient{
		url:    url,
		token:  token,
		client: client,
	}, nil
}

// CreateIssue cria uma nova issue no Jira
func (jc *JiraClient) CreateIssue(title, description string) (*http.Response, error) {
	req, err := http.NewRequest("POST", jc.url+"/rest/api/2/issue", nil)
	if err != nil {
		return nil, err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", jc.token))

	body := fmt.Sprintf(`{
		"fields": {
			"title": "%s",
			"description": "%s"
		}
	}`, title, description)

	req.Body = strings.NewReader(body)
	resp, err := jc.client.Do(req)
	if err != nil {
		return nil, err
	}

	return resp, nil
}

// main é a função principal do programa
func main() {
	jc, err := NewJiraClient("https://your-jira-instance.atlassian.net", "your-jira-token")
	if err != nil {
		fmt.Println("Error creating Jira client:", err)
		return
	}

	title := "New Test Issue"
	description := "This is a test issue created using Go Agent with Jira."

	resp, err := jc.CreateIssue(title, description)
	if err != nil {
		fmt.Println("Error creating issue:", err)
		return
	}
	defer resp.Body.Close()

	fmt.Printf("Response status: %s\n", resp.Status)
}