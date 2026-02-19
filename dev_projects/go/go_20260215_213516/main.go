package main

import (
	"fmt"
	"log"

	"github.com/yourusername/go-agent-jira"
)

func main() {
	// Configuração do Go Agent com Jira
	config := &jira.Config{
		BaseURL: "https://your-jira-instance.atlassian.net",
		UserName: "your-username",
		Password: "your-password",
	}

	// Cria um cliente de Go Agent com Jira
	client, err := jira.NewClient(config)
	if err != nil {
		log.Fatalf("Failed to create client: %v", err)
	}

	// Função para criar uma tarefa no Jira
	createTask := func(title string) error {
		task, err := client.CreateIssue(&jira.Issue{
			Title:    title,
			Description: "This is a test task created by Go Agent",
		})
		if err != nil {
			return fmt.Errorf("Failed to create issue: %v", err)
		}
		fmt.Printf("Task created with ID: %s\n", task.ID)
		return nil
	}

	// Função para atualizar uma tarefa no Jira
	updateTask := func(taskID string, title string) error {
		task, err := client.UpdateIssue(&jira.Issue{
			ID:      taskID,
			Title:    title,
			Description: "This is an updated test task created by Go Agent",
		})
		if err != nil {
			return fmt.Errorf("Failed to update issue: %v", err)
		}
		fmt.Printf("Task updated with ID: %s\n", task.ID)
		return nil
	}

	// Função para deletar uma tarefa no Jira
	deleteTask := func(taskID string) error {
		err := client.DeleteIssue(&jira.Issue{
			ID: taskID,
		})
		if err != nil {
			return fmt.Errorf("Failed to delete issue: %v", err)
		}
		fmt.Printf("Task deleted with ID: %s\n", taskID)
		return nil
	}

	// Exemplo de uso das funções
	err := createTask("Test Task")
	if err != nil {
		log.Fatalf("Error creating task: %v", err)
	}

	err = updateTask("Test Task", "Updated Test Task")
	if err != nil {
		log.Fatalf("Error updating task: %v", err)
	}

	err = deleteTask("Test Task")
	if err != nil {
		log.Fatalf("Error deleting task: %v", err)
	}
}