import React, { useState } from 'react';
import { StyleSheet, Text, View, TouchableOpacity, ScrollView, Image, Alert, ActivityIndicator } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import * as Google from 'expo-auth-session/providers/google';
import AsyncStorage from '@react-native-async-storage/async-storage';

export default function ManualUploadScreen({ navigation }) {
    const [selectedPhotos, setSelectedPhotos] = useState([]);
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState({ current: 0, total: 0 });
    const [googleToken, setGoogleToken] = useState(null);

    // Google Sign-In Configuration
    const [request, response, promptAsync] = Google.useAuthRequest({
        expoClientId: 'YOUR_EXPO_CLIENT_ID',
        iosClientId: 'YOUR_IOS_CLIENT_ID',
        androidClientId: 'YOUR_ANDROID_CLIENT_ID',
        webClientId: 'YOUR_WEB_CLIENT_ID',
        scopes: ['https://www.googleapis.com/auth/drive.file'],
    });

    // Handle Google OAuth
    React.useEffect(() => {
        if (response?.type === 'success') {
            const { authentication } = response;
            setGoogleToken(authentication.accessToken);
            AsyncStorage.setItem('googleToken', authentication.accessToken);
            AsyncStorage.setItem('googleRefreshToken', authentication.refreshToken);
        }
    }, [response]);

    // Request Photo Library Permission
    const requestPermissions = async () => {
        const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (status !== 'granted') {
            Alert.alert('Permission Required', 'Please allow access to your photos.');
            return false;
        }
        return true;
    };

    // Open Photo Gallery Picker
    const pickPhotos = async () => {
        const hasPermission = await requestPermissions();
        if (!hasPermission) return;

        let result = await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ImagePicker.MediaTypeOptions.Images,
            allowsMultipleSelection: true,
            quality: 0.8,
            selectionLimit: 100,
        });

        if (!result.canceled) {
            setSelectedPhotos(result.assets);
        }
    };

    // Upload Photos to Google Drive
    const uploadToDrive = async () => {
        if (!googleToken) {
            Alert.alert('Sign In Required', 'Please sign in with Google first.');
            return;
        }

        if (selectedPhotos.length === 0) {
            Alert.alert('No Photos', 'Please select photos to upload.');
            return;
        }

        setUploading(true);
        setUploadProgress({ current: 0, total: selectedPhotos.length });

        try {
            // Create event folder in Drive
            const eventName = `Event_${new Date().getTime()}`;
            const folderId = await createDriveFolder(googleToken, eventName);

            // Upload each photo
            for (let i = 0; i < selectedPhotos.length; i++) {
                const photo = selectedPhotos[i];
                await uploadPhotoToDrive(googleToken, photo, folderId);
                setUploadProgress({ current: i + 1, total: selectedPhotos.length });
            }

            // Create event in backend with Drive folder ID
            const eventResponse = await fetch('https://nasim-event-app-2025.onrender.com/api/events/manual', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: eventName,
                    drive_folder_id: folderId,
                    photo_count: selectedPhotos.length,
                })
            });

            const eventData = await eventResponse.json();

            setUploading(false);
            Alert.alert('Success!', `QR Code generated! Event ID: ${eventData.event_id}`);
            navigation.navigate('QRCode', { eventId: eventData.event_id });

        } catch (error) {
            setUploading(false);
            Alert.alert('Upload Failed', error.message);
        }
    };

    // Create folder in Google Drive
    const createDriveFolder = async (token, folderName) => {
        const metadata = {
            name: folderName,
            mimeType: 'application/vnd.google-apps.folder',
        };

        const response = await fetch('https://www.googleapis.com/drive/v3/files', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(metadata),
        });

        const data = await response.json();
        return data.id;
    };

    // Upload single photo to Drive
    const uploadPhotoToDrive = async (token, photo, folderId) => {
        const formData = new FormData();
        formData.append('file', {
            uri: photo.uri,
            type: 'image/jpeg',
            name: photo.fileName || `photo_${Date.now()}.jpg`,
        });

        const metadata = {
            name: photo.fileName || `photo_${Date.now()}.jpg`,
            parents: [folderId],
        };

        formData.append('metadata', JSON.stringify(metadata));

        await fetch('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
            },
            body: formData,
        });
    };

    return (
        <View style={styles.container}>
            {/* Header */}
            <View style={styles.header}>
                <Text style={styles.title}>📸 Manual Upload</Text>
                <Text style={styles.subtitle}>Select photos from your camera roll</Text>
            </View>

            {/* Google Sign-In */}
            {!googleToken && (
                <TouchableOpacity style={styles.googleBtn} onPress={() => promptAsync()}>
                    <Text style={styles.googleBtnText}>🔐 Sign in with Google Drive</Text>
                </TouchableOpacity>
            )}

            {/* Photo Picker */}
            {googleToken && !uploading && (
                <TouchableOpacity style={styles.pickerBtn} onPress={pickPhotos}>
                    <Text style={styles.pickerBtnText}>
                        {selectedPhotos.length > 0
                            ? `✓ ${selectedPhotos.length} Photos Selected`
                            : '+ Select Photos'}
                    </Text>
                </TouchableOpacity>
            )}

            {/* Photo Grid */}
            {selectedPhotos.length > 0 && !uploading && (
                <ScrollView style={styles.photoGrid}>
                    <View style={styles.gridContainer}>
                        {selectedPhotos.map((photo, index) => (
                            <Image key={index} source={{ uri: photo.uri }} style={styles.thumbnail} />
                        ))}
                    </View>
                </ScrollView>
            )}

            {/* Upload Button */}
            {selectedPhotos.length > 0 && !uploading && (
                <TouchableOpacity style={styles.uploadBtn} onPress={uploadToDrive}>
                    <Text style={styles.uploadBtnText}>🚀 Upload & Generate QR</Text>
                </TouchableOpacity>
            )}

            {/* Upload Progress */}
            {uploading && (
                <View style={styles.progressContainer}>
                    <ActivityIndicator size="large" color="#667eea" />
                    <Text style={styles.progressText}>
                        Uploading {uploadProgress.current}/{uploadProgress.total} photos...
                    </Text>
                    <View style={styles.progressBar}>
                        <View
                            style={[styles.progressFill, {
                                width: `${(uploadProgress.current / uploadProgress.total) * 100}%`
                            }]}
                        />
                    </View>
                </View>
            )}
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#f8f9fa',
        padding: 20,
    },
    header: {
        marginBottom: 30,
        marginTop: 40,
    },
    title: {
        fontSize: 28,
        fontWeight: 'bold',
        color: '#1a1a2e',
        marginBottom: 8,
    },
    subtitle: {
        fontSize: 16,
        color: '#6c757d',
    },
    googleBtn: {
        backgroundColor: '#4285F4',
        padding: 16,
        borderRadius: 12,
        alignItems: 'center',
        marginBottom: 20,
    },
    googleBtnText: {
        color: 'white',
        fontSize: 16,
        fontWeight: '600',
    },
    pickerBtn: {
        backgroundColor: '#667eea',
        padding: 16,
        borderRadius: 12,
        alignItems: 'center',
        marginBottom: 20,
    },
    pickerBtnText: {
        color: 'white',
        fontSize: 16,
        fontWeight: '600',
    },
    photoGrid: {
        flex: 1,
        marginBottom: 20,
    },
    gridContainer: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
    },
    thumbnail: {
        width: '31%',
        aspectRatio: 1,
        borderRadius: 8,
        marginBottom: 8,
    },
    uploadBtn: {
        backgroundColor: '#28a745',
        padding: 18,
        borderRadius: 12,
        alignItems: 'center',
    },
    uploadBtnText: {
        color: 'white',
        fontSize: 18,
        fontWeight: 'bold',
    },
    progressContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
    },
    progressText: {
        fontSize: 18,
        color: '#1a1a2e',
        marginTop: 20,
        marginBottom: 20,
    },
    progressBar: {
        width: '100%',
        height: 8,
        backgroundColor: '#e9ecef',
        borderRadius: 4,
        overflow: 'hidden',
    },
    progressFill: {
        height: '100%',
        backgroundColor: '#667eea',
    },
});
