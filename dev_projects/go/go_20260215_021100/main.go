package main

import (
	"fmt"
	"net/http"
)

// JiraClient é uma interface para a API do Jira
type JiraClient interface {
	CreateIssue(title string, description string) error
}

// GoAgentClient é uma interface para o Go Agent
type GoAgentClient interface {
	SendData(data map[string]interface{}) error
}

// Jira implements the JiraClient interface
type Jira struct{}

func (j *Jira) CreateIssue(title string, description string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Creating issue: %s - %s\n", title, description)
	return nil
}

// GoAgent implements the GoAgentClient interface
type GoAgent struct{}

func (g *GoAgent) SendData(data map[string]interface{}) error {
	// Simulação de chamada à API do Go Agent
	fmt.Printf("Sending data to Go Agent: %v\n", data)
	return nil
}

// JiraIntegrationHandler é uma função que manipula a requisição HTTP para integrar com Jira
func JiraIntegrationHandler(w http.ResponseWriter, r *http.Request) {
	jiraClient := &Jira{}
	goAgentClient := &GoAgent{}

	title := r.FormValue("title")
	description := r.FormValue("description")

	err := jiraClient.CreateIssue(title, description)
	if err != nil {
		http.Error(w, "Failed to create issue", http.StatusInternalServerError)
		return
	}

	err = goAgentClient.SendData(map[string]interface{}{
		"issueTitle": title,
		"description": description,
	})
	if err != nil {
		http.Error(w, "Failed to send data to Go Agent", http.StatusInternalServerError)
		return
	}

	fmt.Fprintf(w, "Issue created and data sent successfully")
}

func main() {
	http.HandleFunc("/jira-integration", JiraIntegrationHandler)

	fmt.Println("Starting server at :8080")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		fmt.Println(err)
	}
}