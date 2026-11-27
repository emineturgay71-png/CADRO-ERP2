import _ from "@/lib/translate"
import { useFrappeGetDocList } from "frappe-react-sdk"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Loader2Icon } from "lucide-react"

type PostingProfile = {
    name: string
    profile_name: string
    company: string
    disabled?: 0 | 1
    strict_mode?: 0 | 1
}

const GLPostingProfiles = () => {
    const { data, isLoading, error } = useFrappeGetDocList<PostingProfile>("GL Posting Profile", {
        fields: ["name", "profile_name", "company", "disabled", "strict_mode"],
        orderBy: { field: "modified", order: "desc" },
        limit: 200,
    })

    if (error) return <div className="p-4 text-destructive">{_("Failed to load posting profiles.")}</div>

    return (
        <div className="flex flex-col gap-4">
            {isLoading ? (
                <div className="flex items-center justify-center p-16"><Loader2Icon className="size-6 animate-spin text-muted-foreground" /></div>
            ) : (
                <div className="border rounded-lg overflow-hidden">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>{_("Profile Name")}</TableHead>
                                <TableHead>{_("Company")}</TableHead>
                                <TableHead>{_("Strict Mode")}</TableHead>
                                <TableHead>{_("Disabled")}</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {data?.map(p => (
                                <TableRow key={p.name}>
                                    <TableCell className="font-medium">{p.profile_name}</TableCell>
                                    <TableCell>{p.company}</TableCell>
                                    <TableCell>{p.strict_mode ? <Badge theme="red">{_("Strict")}</Badge> : <Badge theme="gray">{_("Off")}</Badge>}</TableCell>
                                    <TableCell>{p.disabled ? <Badge theme="red">{_("Yes")}</Badge> : <Badge theme="green">{_("No")}</Badge>}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            )}
        </div>
    )
}

export default GLPostingProfiles
