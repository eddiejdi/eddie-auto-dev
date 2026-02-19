import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraManagerFactory;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;

public class JavaAgent {

    public static void main(String[] args) {
        // Inicializa o Jira
        Jira jira = JiraManagerFactory.getJiraInstance();

        // Obtém o CustomFieldManager e FieldManager
        CustomFieldManager customFieldManager = jira.getComponent(CustomFieldManager.class);
        FieldManager fieldManager = jira.getComponent(FieldManager.class);

        // Obtém o ProjectManager
        ProjectManager projectManager = jira.getComponent(ProjectManager.class);

        // Cria um novo projeto (exemplo)
        Project project = new Project("MyProject", "My Project Description");

        // Adiciona o projeto ao Jira
        projectManager.addProject(project);

        // Cria uma nova tarefa (exemplo)
        Issue issue = new Issue(project, "Task1", "This is a task description");
        fieldManager.updateIssue(issue);

        // Monitoramento de atividades e gerenciamento de tarefas
        // ...

        // Relatórios detalhados
        // ...
    }
}