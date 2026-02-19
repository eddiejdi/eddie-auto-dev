import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraException;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.user.User;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class JavaAgent {

    @Autowired
    private Jira jira;

    public void monitorarAtividades() {
        try {
            Project project = jira.getProject("YOUR_PROJECT_KEY");
            FieldManager fieldManager = jira.getFieldManager();
            CustomFieldManager customFieldManager = jira.getCustomFieldManager();

            // Exemplo: Monitorar tarefas com status "In Progress"
            Issue[] issues = project.getIssuesByStatus("In Progress");

            for (Issue issue : issues) {
                User reporter = fieldManager.getUserObject(issue.getReporterId());
                String reporterName = reporter.getName();
                String summary = issue.getSummary();

                System.out.println("Tarefa: " + summary);
                System.out.println("Reportado por: " + reporterName);
                System.out.println("------------------------");
            }
        } catch (JiraException e) {
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        JavaAgent agent = new JavaAgent();
        agent.monitorarAtividades();
    }
}