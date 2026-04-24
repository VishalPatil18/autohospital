"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/components/auth-provider";
import Nav from "@/components/nav";
import { get } from "@/lib/api";

interface Patient {
  user_id: string;
  first_name: string;
  last_name: string;
  dob: string;
  phone: string | null;
  address: string | null;
}

interface Appointment {
  id: string;
  patient_id: string;
  doctor_id: string;
  scheduled_at: string;
  status: string;
  notes: string | null;
  created_at: string;
}

interface ClinicalNote {
  id: string;
  appointment_id: string;
  soap_text: string;
  signed_at: string | null;
  ingestion_status: string;
}

interface PatientNote {
  id: string;
  appointment_id: string;
  plain_text: string;
}

interface Document {
  id: string;
  patient_id: string;
  filename: string;
  ingestion_status: string;
  uploaded_at: string;
}

interface TimelineItem {
  type: "appointment" | "clinical_note" | "patient_note";
  date: Date;
  data: Appointment | ClinicalNote | PatientNote;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatTime(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function TimelineEvent({ item }: { item: TimelineItem }) {
  const isAppointment = item.type === "appointment";
  const isClinicalNote = item.type === "clinical_note";

  if (isAppointment) {
    const apt = item.data as Appointment;
    return (
      <div className="flex gap-4">
        <div className="flex flex-col items-center">
          <div className="w-3 h-3 bg-blue-600 rounded-full mt-1.5" />
          <div className="w-0.5 h-24 bg-slate-200 mt-2" />
        </div>
        <div className="pb-8">
          <p className="text-sm font-semibold text-slate-900">Appointment</p>
          <p className="text-sm text-slate-500">
            {formatDate(apt.scheduled_at)} at {formatTime(apt.scheduled_at)}
          </p>
          <p className="text-sm text-slate-600 mt-1 capitalize">{apt.status}</p>
          {apt.notes && <p className="text-sm text-slate-600 mt-2">{apt.notes}</p>}
        </div>
      </div>
    );
  }

  if (isClinicalNote) {
    const note = item.data as ClinicalNote;
    return (
      <div className="flex gap-4">
        <div className="flex flex-col items-center">
          <div className="w-3 h-3 bg-green-600 rounded-full mt-1.5" />
          <div className="w-0.5 h-20 bg-slate-200 mt-2" />
        </div>
        <div className="pb-8">
          <p className="text-sm font-semibold text-slate-900">Clinical Note</p>
          <p className="text-sm text-slate-600 mt-2 line-clamp-3">{note.soap_text}</p>
          <p className="text-xs text-slate-400 mt-2">
            {note.signed_at ? `Signed: ${formatDate(note.signed_at)}` : "Unsigned"}
          </p>
        </div>
      </div>
    );
  }

  const pnote = item.data as PatientNote;
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <div className="w-3 h-3 bg-purple-600 rounded-full mt-1.5" />
        <div className="w-0.5 h-20 bg-slate-200 mt-2" />
      </div>
      <div className="pb-8">
        <p className="text-sm font-semibold text-slate-900">Patient Note</p>
        <p className="text-sm text-slate-600 mt-2 line-clamp-3">{pnote.plain_text}</p>
      </div>
    </div>
  );
}

export default function PatientDashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [patient, setPatient] = useState<Patient | null>(null);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [notes, setNotes] = useState<{
    clinical_notes: ClinicalNote[];
    patient_notes: PatientNote[];
  }>({ clinical_notes: [], patient_notes: [] });
  const [documents, setDocuments] = useState<Document[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [dataLoading, setDataLoading] = useState(true);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
    if (!loading && user && user.role !== "patient") {
      router.push("/doctor/dashboard");
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (!loading && user) {
      fetchPatientData();
    }
  }, [user, loading]);

  async function fetchPatientData() {
    try {
      setDataLoading(true);
      setError(null);

      const [patientData, appointmentsData, notesData, documentsData] = await Promise.all([
        get<Patient>("/api/patients/me"),
        get<Appointment[]>("/api/patients/me/appointments"),
        get<any>("/api/patients/me/notes"),
        get<Document[]>("/api/patients/me/documents"),
      ]);

      setPatient(patientData);
      setAppointments(appointmentsData);
      setNotes(notesData);
      setDocuments(documentsData);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load dashboard data";
      setError(message);
      console.error("Error fetching patient data:", err);
    } finally {
      setDataLoading(false);
    }
  }

  if (loading || dataLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-slate-400 text-sm">Loading...</div>
      </div>
    );
  }

  if (!user) return null;

  // Build timeline
  const timelineItems: TimelineItem[] = [];

  appointments.forEach((apt) => {
    timelineItems.push({
      type: "appointment",
      date: new Date(apt.scheduled_at),
      data: apt,
    });
  });

  notes.clinical_notes.forEach((note) => {
    // Use appointment scheduled_at as date, or fall back to now
    const apt = appointments.find((a) => a.id === note.appointment_id);
    timelineItems.push({
      type: "clinical_note",
      date: apt ? new Date(apt.scheduled_at) : new Date(),
      data: note,
    });
  });

  notes.patient_notes.forEach((note) => {
    const apt = appointments.find((a) => a.id === note.appointment_id);
    timelineItems.push({
      type: "patient_note",
      date: apt ? new Date(apt.scheduled_at) : new Date(),
      data: note,
    });
  });

  // Sort by date descending
  timelineItems.sort((a, b) => b.date.getTime() - a.date.getTime());

  const upcomingCount = appointments.filter(
    (a) => a.status === "scheduled" && new Date(a.scheduled_at) > new Date()
  ).length;

  return (
    <div className="min-h-screen bg-slate-50">
      <Nav />

      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900">
            Welcome, {patient?.first_name || user?.email}
          </h1>
          <p className="text-slate-500 mt-1">
            Here&apos;s an overview of your health information.
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-8 text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Stats row */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <p className="text-sm text-slate-500">Upcoming Appointments</p>
            <p className="text-3xl font-bold text-slate-900 mt-1">{upcomingCount}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <p className="text-sm text-slate-500">Documents</p>
            <p className="text-3xl font-bold text-slate-900 mt-1">{documents.length}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <p className="text-sm text-slate-500">Recent Notes</p>
            <p className="text-3xl font-bold text-slate-900 mt-1">
              {notes.clinical_notes.length + notes.patient_notes.length}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Timeline */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-6">Activity Timeline</h2>
              {timelineItems.length === 0 ? (
                <p className="text-slate-500 text-sm">No activity yet</p>
              ) : (
                <div>{timelineItems.map((item) => (
                  <TimelineEvent key={`${item.type}-${item.data.id}`} item={item} />
                ))}</div>
              )}
            </div>
          </div>

          {/* Documents sidebar */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900">Documents</h2>
              <Link
                href="/patient/documents"
                className="text-sm text-blue-600 hover:text-blue-700 font-medium"
              >
                View all →
              </Link>
            </div>
            <div className="space-y-3">
              {documents.length === 0 ? (
                <p className="text-slate-500 text-sm">No documents yet</p>
              ) : (
                documents.slice(0, 5).map((doc) => (
                  <div
                    key={doc.id}
                    className="p-3 rounded-lg bg-slate-50 border border-slate-100 hover:bg-slate-100 transition cursor-pointer"
                  >
                    <p className="text-sm font-medium text-slate-900 truncate">
                      {doc.filename}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                      {formatDate(doc.uploaded_at)}
                    </p>
                    <p className="text-xs text-slate-400 mt-1 capitalize">
                      {doc.ingestion_status}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
